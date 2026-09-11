import * as THREE from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js"
import { fetchSceneAsset } from "./api"
import { blocksWalkAt } from "./collision"
import type { CampusRuntime, CampusViewState, ModelCampusManifest, PixelPoint } from "./types"

export function createCampusRuntime(
  container: HTMLElement,
  manifest: ModelCampusManifest,
  signal: AbortSignal,
  onState: (state: CampusViewState) => void,
  onReady: () => void,
  onError: (error: Error) => void,
): CampusRuntime {
  const { world } = manifest
  const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.13
  renderer.domElement.style.cssText = "width:100%;height:100%;display:block;touch-action:none"
  container.append(renderer.domElement)
  const scene = new THREE.Scene()
  scene.background = new THREE.Color("#c9dbe4")
  scene.fog = new THREE.Fog("#c9dbe4", 550, 1400)
  const camera = new THREE.PerspectiveCamera(42, 1, 0.15, 2200)
  const controls = new OrbitControls(camera, renderer.domElement)
  Object.assign(controls, { enableDamping: true, dampingFactor: 0.07, maxPolarAngle: Math.PI * 0.488, minDistance: 15, maxDistance: 700 })
  const ambient = new THREE.HemisphereLight("#deefff", "#8c9276", 2.2)
  const sun = new THREE.DirectionalLight("#fff0d9", 3.2)
  sun.position.set(-145, 240, -155)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  Object.assign(sun.shadow.camera, { left: -330, right: 330, top: 330, bottom: -330, near: 1, far: 700 })
  sun.shadow.bias = -0.00015
  sun.shadow.normalBias = 0.5
  const fill = new THREE.DirectionalLight("#b4c8dc", 0.5)
  fill.position.set(150, 100, 170)
  scene.add(ambient, sun, fill)
  const px = ([u, v]: PixelPoint, h = 1.9) => new THREE.Vector3((u - world.originPixel[0]) * world.metresPerPixel, h, (v - world.originPixel[1]) * world.metresPerPixel)
  const nightLights = world.lights.map((p) => {
    const light = new THREE.PointLight("#ffdca5", 0, 36, 2)
    light.position.copy(px(p, 7))
    scene.add(light)
    return light
  })
  const obstacles = world.buildings.map((b) =>
    b.polygon.map((point): PixelPoint => {
      const p = px(point)
      return [p.x, p.z]
    }),
  )
  const water = world.water.map((poly) => poly.map((p) => px(p)))
  let disposed = false
  let ready = false
  let frame = 0
  let yaw = 0
  let pitch = 0
  let last = performance.now()
  let drag: { x: number; y: number } | null = null
  let state: CampusViewState = { mode: "orbit", entry: null, night: false }
  const keys = new Set<string>()
  const events = new AbortController()
  function publish() {
    onState({ ...state })
  }
  function home(top = false) {
    state = { ...state, mode: "orbit", entry: null }
    keys.clear()
    controls.enabled = true
    controls.target.fromArray(world.orbitTarget)
    camera.position.fromArray(top ? [world.orbitTarget[0], 355, world.orbitTarget[2] + 0.01] : world.orbitPosition)
    camera.lookAt(controls.target)
    controls.update()
    publish()
  }
  function enter(id: string) {
    const entry = world.entries.find((e) => e.id === id)
    if (!entry || !ready) return
    controls.enabled = false
    keys.clear()
    camera.position.copy(px(entry.pixel))
    yaw = entry.yaw
    pitch = 0
    camera.rotation.set(pitch, yaw, 0, "YXZ")
    state = { ...state, mode: "walk", entry: id }
    container.focus()
    publish()
  }
  function inside(p: THREE.Vector3, poly: THREE.Vector3[]) {
    let value = false
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const a = poly[i],
        b = poly[j]
      if (a.z > p.z !== b.z > p.z && p.x < ((b.x - a.x) * (p.z - a.z)) / (b.z - a.z) + a.x) value = !value
    }
    return value
  }
  function canWalk(p: THREE.Vector3) {
    const [minX, maxX, minZ, maxZ] = world.walkBounds
    return p.x >= minX && p.x <= maxX && p.z >= minZ && p.z <= maxZ && !water.some((poly) => inside(p, poly)) && !obstacles.some((polygon) => blocksWalkAt([p.x, p.z], polygon))
  }
  function move(forward: number, right: number, distance: number) {
    if (state.mode !== "walk") return
    const delta = new THREE.Vector3(-Math.sin(yaw) * forward + Math.cos(yaw) * right, 0, -Math.cos(yaw) * forward - Math.sin(yaw) * right).normalize().multiplyScalar(distance)
    const p = camera.position.clone()
    p.x += delta.x
    if (canWalk(p)) camera.position.x = p.x
    p.copy(camera.position)
    p.z += delta.z
    if (canWalk(p)) camera.position.z = p.z
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
        camera.rotation.set(pitch, yaw, 0, "YXZ")
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
  renderer.domElement.addEventListener(
    "pointerdown",
    (e) => {
      container.focus()
      if (state.mode === "walk") {
        drag = { x: e.clientX, y: e.clientY }
        renderer.domElement.setPointerCapture(e.pointerId)
      }
    },
    { signal: events.signal },
  )
  renderer.domElement.addEventListener(
    "pointermove",
    (e) => {
      if (state.mode !== "walk" || !drag) return
      yaw -= (e.clientX - drag.x) * 0.004
      pitch = THREE.MathUtils.clamp(pitch - (e.clientY - drag.y) * 0.004, -1.2, 1.2)
      drag = { x: e.clientX, y: e.clientY }
      camera.rotation.set(pitch, yaw, 0, "YXZ")
    },
    { signal: events.signal },
  )
  for (const event of ["pointerup", "pointercancel"] as const)
    renderer.domElement.addEventListener(
      event,
      () => {
        drag = null
      },
      { signal: events.signal },
    )
  const resize = () => {
    const rect = container.getBoundingClientRect()
    if (!rect.width || !rect.height || disposed) return
    camera.aspect = rect.width / rect.height
    camera.updateProjectionMatrix()
    renderer.setSize(rect.width, rect.height, false)
  }
  const observer = new ResizeObserver(resize)
  observer.observe(container)
  window.addEventListener("resize", resize, { signal: events.signal })
  resize()
  function animate(now: number) {
    if (disposed) return
    frame = requestAnimationFrame(animate)
    const dt = Math.min((now - last) / 1000, 0.06)
    last = now
    if (state.mode === "orbit") controls.update()
    else move(Number(keys.has("forward")) - Number(keys.has("back")), Number(keys.has("right")) - Number(keys.has("left")), dt * (keys.has("fast") ? 9 : 3))
    renderer.render(scene, camera)
  }
  const disposeObject = (object: THREE.Object3D) =>
    object.traverse((node) => {
      if (!(node instanceof THREE.Mesh)) return
      node.geometry.dispose()
      for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose()
        material.dispose()
      }
    })
  async function load() {
    try {
      const loader = new GLTFLoader()
      for (const asset of manifest.assets) {
        const response = await fetchSceneAsset(asset, manifest.teamId, signal)
        const buffer = await response.arrayBuffer()
        if (disposed || signal.aborted) return
        const model = await loader.parseAsync(buffer, "")
        if (disposed || signal.aborted) {
          disposeObject(model.scene)
          return
        }
        const ground = asset.includes("ground.glb")
        model.scene.traverse((node) => {
          if (!(node instanceof THREE.Mesh)) return
          node.castShadow = ground ? /foliage|bark|tree/i.test(node.name) : /_(wall|roof|shelter|equipment|base)$/.test(node.name)
          node.receiveShadow = true
          if (ground) for (const material of Array.isArray(node.material) ? node.material : [node.material]) material.side = THREE.DoubleSide
        })
        scene.add(model.scene)
      }
      if (!disposed && !signal.aborted) {
        ready = true
        onReady()
      }
    } catch (error) {
      if (!disposed && !signal.aborted) onError(error instanceof Error ? error : new Error("模型加载失败"))
    }
  }
  home()
  frame = requestAnimationFrame(animate)
  void load()
  return {
    home,
    enter,
    move: (direction) => {
      container.focus()
      move(direction === "forward" ? 1 : direction === "back" ? -1 : 0, direction === "right" ? 1 : direction === "left" ? -1 : 0, 1)
    },
    toggleNight: () => {
      state = { ...state, night: !state.night }
      const color = state.night ? "#142433" : "#c9dbe4"
      ;(scene.background as THREE.Color).set(color)
      ;(scene.fog as THREE.Fog).color.set(color)
      sun.intensity = state.night ? 0.13 : 3.2
      ambient.intensity = state.night ? 0.42 : 2.2
      fill.intensity = state.night ? 0.2 : 0.5
      renderer.toneMappingExposure = state.night ? 1.3 : 1.13
      for (const light of nightLights) light.intensity = state.night ? 280 : 0
      publish()
    },
    dispose: () => {
      if (disposed) return
      disposed = true
      cancelAnimationFrame(frame)
      events.abort()
      observer.disconnect()
      controls.dispose()
      disposeObject(scene)
      sun.shadow.map?.dispose()
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
    },
  }
}
