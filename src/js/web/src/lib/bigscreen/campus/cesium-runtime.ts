import "cesium/Build/Cesium/Widgets/widgets.css"
import { Axis, Cartesian3, Color, DirectionalLight, EllipsoidTerrainProvider, Matrix4, Model, ShadowMode, UrlTemplateImageryProvider, Viewer } from "cesium"
import { fetchSceneAsset } from "./api"
import { blocksWalkAt } from "./collision"
import { campusModelMatrix, campusPointToFixed } from "./georegistration"
import type { CampusRuntime, CampusViewState, ModelCampusManifest, PixelPoint } from "./types"

/** Geographic renderer for the same tenant GLBs and controls used by the local viewer. */
export function createCesiumCampusRuntime(
  container: HTMLElement,
  manifest: ModelCampusManifest,
  signal: AbortSignal,
  onState: (state: CampusViewState) => void,
  onReady: () => void,
  onError: (error: Error) => void,
): CampusRuntime {
  if (manifest.engine !== "cesium-campus") throw new Error("园区地图定位配置缺失")
  const { world, georegistration: registration } = manifest
  const matrix = campusModelMatrix(registration)
  const viewer = new Viewer(container, {
    baseLayer: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    terrainProvider: new EllipsoidTerrainProvider(),
    requestRenderMode: true,
    maximumRenderTimeChange: Infinity,
    shadows: false,
  })
  viewer.resolutionScale = Math.min(window.devicePixelRatio, 1.5)
  viewer.scene.globe.depthTestAgainstTerrain = true
  viewer.scene.globe.enableLighting = false
  viewer.scene.globe.baseColor = Color.fromCssColorString("#889a94")
  viewer.scene.screenSpaceCameraController.minimumZoomDistance = 1
  viewer.scene.screenSpaceCameraController.maximumZoomDistance = 30000
  const provider = new UrlTemplateImageryProvider(registration.imagery)
  const imagery = viewer.imageryLayers.addImageryProvider(provider)
  const lightDirection = Matrix4.multiplyByPointAsVector(matrix, new Cartesian3(0.3, -0.4, -1), new Cartesian3())
  viewer.scene.light = new DirectionalLight({ direction: Cartesian3.normalize(lightDirection, lightDirection), intensity: 2.5 })
  let disposed = false
  let ready = false
  let failed = false
  let loadedCount = 0
  let frame = 0
  let last = performance.now()
  let state: CampusViewState = { mode: "orbit", entry: null, night: false }
  let yaw = 0
  let pitch = 0
  let position: PixelPoint = [0, 0]
  let drag: { x: number; y: number } | null = null
  const events = new AbortController()
  const urls = new Set<string>()
  const keys = new Set<string>()
  const pixelLocal = ([u, v]: PixelPoint): PixelPoint => [(u - world.originPixel[0]) * world.metresPerPixel, (v - world.originPixel[1]) * world.metresPerPixel]
  const obstacles = world.buildings.map((b) => b.polygon.map(pixelLocal))
  const waters = world.water.map((ring) => ring.map(pixelLocal))
  const lamps = world.lights.map((pixel) => {
    const [x, z] = pixelLocal(pixel)
    return viewer.entities.add({
      position: campusPointToFixed(matrix, x, 7, z),
      show: false,
      point: { pixelSize: 5, color: Color.fromCssColorString("#ffdc95"), outlineColor: Color.fromCssColorString("#bc945644"), outlineWidth: 3 },
    })
  })
  function publish() {
    onState({ ...state })
  }
  function fail(error: Error) {
    if (!disposed && !signal.aborted) {
      failed = true
      onError(error)
    }
  }
  const removeRenderError = viewer.scene.renderError.addEventListener((_scene, error) => fail(error instanceof Error ? error : new Error("地图渲染失败")))
  const removeImageryError = provider.errorEvent.addEventListener(() => fail(new Error("卫星底图加载失败，请检查网络后刷新")))
  function home(top = false) {
    if (disposed) return
    state = { ...state, mode: "orbit", entry: null }
    keys.clear()
    drag = null
    viewer.scene.screenSpaceCameraController.enableInputs = true
    const [tx, ty, tz] = world.orbitTarget
    const [cx, cy, cz] = top ? [tx, 355, tz + 0.01] : world.orbitPosition
    const target = campusPointToFixed(matrix, tx, ty, tz)
    viewer.camera.lookAt(target, new Cartesian3((cx - tx) * registration.scale[0], -(cz - tz) * registration.scale[1], cy - ty))
    viewer.camera.lookAtTransform(Matrix4.IDENTITY)
    viewer.scene.requestRender()
    publish()
  }
  function updateWalker() {
    viewer.camera.setView({
      destination: campusPointToFixed(matrix, position[0], 1.9, position[1]),
      orientation: { heading: -yaw, pitch, roll: 0 },
    })
    viewer.scene.requestRender()
  }
  function enter(id: string) {
    const entry = world.entries.find((e) => e.id === id)
    if (!entry || !ready || disposed) return
    viewer.scene.screenSpaceCameraController.enableInputs = false
    keys.clear()
    drag = null
    position = pixelLocal(entry.pixel)
    yaw = entry.yaw
    pitch = 0
    state = { ...state, mode: "walk", entry: id }
    updateWalker()
    container.focus()
    publish()
  }
  function canWalk(point: PixelPoint) {
    const [x, z] = point
    const [minX, maxX, minZ, maxZ] = world.walkBounds
    return x >= minX && x <= maxX && z >= minZ && z <= maxZ && !obstacles.some((p) => blocksWalkAt(point, p)) && !waters.some((p) => blocksWalkAt(point, p, 0))
  }
  function move(forward: number, right: number, distance: number) {
    if (disposed || state.mode !== "walk" || (!forward && !right)) return
    const length = Math.hypot(forward, right)
    const dx = ((-Math.sin(yaw) * forward + Math.cos(yaw) * right) * distance) / length
    const dz = ((-Math.cos(yaw) * forward - Math.sin(yaw) * right) * distance) / length
    if (canWalk([position[0] + dx, position[1]])) position[0] += dx
    if (canWalk([position[0], position[1] + dz])) position[1] += dz
    updateWalker()
  }
  const keyMap: Record<string, string> = {
    KeyW: "forward",
    ArrowUp: "forward",
    KeyS: "back",
    ArrowDown: "back",
    KeyA: "left",
    ArrowLeft: "left",
    KeyD: "right",
    ArrowRight: "right",
  }
  window.addEventListener(
    "keydown",
    (e) => {
      if (!container.parentElement?.contains(document.activeElement)) return
      if (e.code === "Escape") {
        home()
        return
      }
      if (state.mode !== "walk") return
      if (e.code === "KeyQ" || e.code === "KeyE") {
        e.preventDefault()
        yaw += e.code === "KeyQ" ? 0.12 : -0.12
        updateWalker()
      }
      if (keyMap[e.code]) {
        e.preventDefault()
        if (!e.repeat) move(keyMap[e.code] === "forward" ? 1 : keyMap[e.code] === "back" ? -1 : 0, keyMap[e.code] === "right" ? 1 : keyMap[e.code] === "left" ? -1 : 0, 0.35)
        keys.add(keyMap[e.code])
      }
      if (e.code.startsWith("Shift")) keys.add("fast")
    },
    { signal: events.signal },
  )
  window.addEventListener(
    "keyup",
    (e) => {
      keys.delete(keyMap[e.code])
      if (e.code.startsWith("Shift")) keys.delete("fast")
    },
    { signal: events.signal },
  )
  window.addEventListener("blur", () => keys.clear(), { signal: events.signal })
  viewer.canvas.addEventListener(
    "pointerdown",
    (e) => {
      container.focus()
      if (state.mode === "walk") {
        drag = { x: e.clientX, y: e.clientY }
        viewer.canvas.setPointerCapture(e.pointerId)
      }
    },
    { signal: events.signal },
  )
  viewer.canvas.addEventListener(
    "pointermove",
    (e) => {
      if (state.mode !== "walk" || !drag) return
      yaw -= (e.clientX - drag.x) * 0.004
      pitch = Math.max(-1.2, Math.min(1.2, pitch - (e.clientY - drag.y) * 0.004))
      drag = { x: e.clientX, y: e.clientY }
      updateWalker()
    },
    { signal: events.signal },
  )
  for (const event of ["pointerup", "pointercancel"] as const)
    viewer.canvas.addEventListener(
      event,
      () => {
        drag = null
      },
      { signal: events.signal },
    )
  const observer = new ResizeObserver(() => {
    if (!disposed) {
      viewer.resize()
      viewer.scene.requestRender()
    }
  })
  observer.observe(container)
  function animate(now: number) {
    if (disposed) return
    const dt = Math.min((now - last) / 1000, 0.06)
    last = now
    move(Number(keys.has("forward")) - Number(keys.has("back")), Number(keys.has("right")) - Number(keys.has("left")), dt * (keys.has("fast") ? 9 : 3))
    frame = requestAnimationFrame(animate)
  }
  async function load() {
    try {
      if (!manifest.assets.length) throw new Error("园区模型资源缺失")
      await Promise.all(
        manifest.assets.map(async (asset) => {
          const response = await fetchSceneAsset(asset, manifest.teamId, signal)
          const blob = await response.blob()
          if (disposed || signal.aborted) return
          const url = URL.createObjectURL(blob)
          urls.add(url)
          const model = await Model.fromGltfAsync({
            url,
            modelMatrix: matrix,
            upAxis: Axis.Y,
            forwardAxis: Axis.X,
            scale: 1,
            minimumPixelSize: 0,
            shadows: ShadowMode.DISABLED,
          })
          if (disposed || signal.aborted) {
            model.destroy()
            return
          }
          model.errorEvent.addEventListener((error) => fail(error))
          const modelReady = () => {
            loadedCount += 1
            if (!disposed && !failed && loadedCount === manifest.assets.length) {
              ready = true
              onReady()
            }
          }
          if (model.ready) modelReady()
          else model.readyEvent.addEventListener(modelReady)
          viewer.scene.primitives.add(model)
          viewer.scene.requestRender()
        }),
      )
    } catch (error) {
      fail(error instanceof Error ? error : new Error("园区模型加载失败"))
    }
  }
  function dispose() {
    if (disposed) return
    disposed = true
    ready = false
    events.abort()
    keys.clear()
    observer.disconnect()
    cancelAnimationFrame(frame)
    removeRenderError()
    removeImageryError()
    viewer.destroy()
    for (const url of urls) URL.revokeObjectURL(url)
    urls.clear()
    signal.removeEventListener("abort", dispose)
  }
  signal.addEventListener("abort", dispose, { once: true })
  home()
  frame = requestAnimationFrame(animate)
  void load()
  return {
    home,
    enter,
    dispose,
    move: (direction) => {
      container.focus()
      move(direction === "forward" ? 1 : direction === "back" ? -1 : 0, direction === "right" ? 1 : direction === "left" ? -1 : 0, 1)
    },
    toggleNight: () => {
      if (disposed) return
      state = { ...state, night: !state.night }
      viewer.scene.light.intensity = state.night ? 0.35 : 2.5
      imagery.brightness = state.night ? 0.35 : 1
      if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = !state.night
      viewer.scene.backgroundColor = Color.fromCssColorString(state.night ? "#142433" : "#c9dbe4")
      for (const lamp of lamps) lamp.show = state.night
      viewer.scene.requestRender()
      publish()
    },
  }
}
