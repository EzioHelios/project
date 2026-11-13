import * as THREE from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js"

const root = document.querySelector("#canvas")
const select = document.querySelector("#site")
const status = document.querySelector("#status")
const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true })
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2))
renderer.outputColorSpace = THREE.SRGBColorSpace
renderer.toneMapping = THREE.ACESFilmicToneMapping
renderer.toneMappingExposure = 1.08
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFSoftShadowMap
root.append(renderer.domElement)

const scene = new THREE.Scene()
scene.background = new THREE.Color(0x1d282d)
scene.add(new THREE.HemisphereLight(0xdff1f7, 0x72827d, 1.5))
const sun = new THREE.DirectionalLight(0xfff5de, 2.5)
sun.position.set(-120, 220, 155)
sun.castShadow = true
sun.shadow.mapSize.set(2048, 2048)
Object.assign(sun.shadow.camera, { left: -270, right: 270, top: 270, bottom: -270, near: 1, far: 700 })
sun.shadow.bias = -0.00015
sun.shadow.normalBias = 0.18
scene.add(sun)

const camera = new THREE.PerspectiveCamera(44, 1, 0.5, 2200)
const controls = new OrbitControls(camera, renderer.domElement)
controls.enableDamping = true
controls.maxPolarAngle = Math.PI / 2 - 0.02
controls.minDistance = 16
controls.maxDistance = 1600
const loader = new GLTFLoader()
let model = null
let loadId = 0

function frame(object) {
  const bounds = new THREE.Box3().setFromObject(object)
  const center = bounds.getCenter(new THREE.Vector3())
  const size = bounds.getSize(new THREE.Vector3())
  controls.target.copy(center)
  const direction = new THREE.Vector3(1, 0.8, 1).normalize()
  const radius = size.length() / 2
  const halfVerticalFov = THREE.MathUtils.degToRad(camera.fov / 2)
  const halfHorizontalFov = Math.atan(Math.tan(halfVerticalFov) * camera.aspect)
  const distance = (radius / Math.sin(Math.min(halfVerticalFov, halfHorizontalFov))) * 1.12
  camera.position.copy(center).addScaledVector(direction, distance)
  camera.lookAt(center)
  camera.updateProjectionMatrix()
  controls.update()
}

async function loadSite(site) {
  const current = ++loadId
  document.body.dataset.sceneReady = "false"
  status.textContent = "正在加载模型"
  const prefix = `/src/py/app/assets/scenes/packs/woheng-${site}-v1`
  try {
    const [ground, buildings] = await Promise.all([
      loader.loadAsync(`${prefix}/ground.glb`),
      loader.loadAsync(`${prefix}/buildings.glb`),
    ])
    if (current !== loadId) return
    if (model) scene.remove(model)
    model = new THREE.Group()
    ground.scene.traverse((node) => { if (node.isMesh) node.receiveShadow = true })
    buildings.scene.traverse((node) => { if (node.isMesh) node.castShadow = true })
    model.add(ground.scene, buildings.scene)
    scene.add(model)
    frame(model)
    status.textContent = "演示模型 · 厂区布局为虚构设定"
    document.body.dataset.sceneReady = "true"
  } catch (error) {
    status.textContent = `模型加载失败：${error instanceof Error ? error.message : String(error)}`
    document.body.dataset.sceneReady = "error"
  }
}

function resize() {
  renderer.setSize(root.clientWidth, root.clientHeight)
  camera.aspect = root.clientWidth / root.clientHeight
  camera.updateProjectionMatrix()
}
window.addEventListener("resize", resize)
select.addEventListener("change", () => {
  history.replaceState(null, "", `?site=${select.value}`)
  loadSite(select.value)
})
select.value = new URLSearchParams(location.search).get("site") === "huzhou" ? "huzhou" : "taizhou"
resize()
loadSite(select.value)
renderer.setAnimationLoop(() => {
  controls.update()
  renderer.render(scene, camera)
})
