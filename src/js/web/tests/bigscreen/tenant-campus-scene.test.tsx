import { render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { TenantCampusScene } from "@/components/bigscreen/campus/tenant-campus-scene"
import { SceneNotConfiguredError } from "@/lib/bigscreen/campus/api"

const mocks = vi.hoisted(() => ({ teamId: "team-a", fetch: vi.fn(), mount: vi.fn(), cesiumMount: vi.fn(), dispose: vi.fn() }))
vi.mock("@/lib/auth", () => ({ useAuthStore: (selector: (state: unknown) => unknown) => selector({ currentTeam: { id: mocks.teamId } }) }))
vi.mock("@/components/bigscreen/scene-canvas", () => ({ BigscreenSceneCanvas: () => <div>Legacy scene</div> }))
vi.mock("@/lib/bigscreen/campus/api", () => ({ fetchSceneManifest: mocks.fetch, fetchSceneAsset: vi.fn(), SceneNotConfiguredError: class extends Error {} }))
vi.mock("@/lib/bigscreen/campus/runtime", () => ({ createCampusRuntime: mocks.mount }))
vi.mock("@/lib/bigscreen/campus/cesium-runtime", () => ({ createCesiumCampusRuntime: mocks.cesiumMount }))
const manifest = (id: string) => ({ engine: "three", teamId: id, sceneId: id, title: id, revision: "1", assets: [], world: { entries: [] } })
beforeEach(() => {
  mocks.teamId = "team-a"
  mocks.fetch.mockReset(); mocks.mount.mockReset(); mocks.dispose.mockReset()
  mocks.mount.mockImplementation((_node, _manifest, _signal, _onState, ready) => { ready(); return { dispose: mocks.dispose, home: vi.fn() } })
  mocks.cesiumMount.mockReset()
  mocks.cesiumMount.mockImplementation((_node, _manifest, _signal, _onState, ready) => { ready(); return { dispose: mocks.dispose, home: vi.fn() } })
})
afterEach(() => vi.clearAllMocks())
describe("tenant campus lifecycle", () => {
  it("loads geographic assets through the Cesium runtime and destroys them on tenant switch", async () => {
    mocks.fetch.mockImplementation((id: string) => Promise.resolve({ ...manifest(id), engine: "cesium-campus" }))
    const view = render(<TenantCampusScene showControls />)
    await waitFor(() => expect(mocks.cesiumMount).toHaveBeenCalledTimes(1))
    expect(mocks.mount).not.toHaveBeenCalled()
    expect(view.container.querySelector('[data-scene-engine="cesium-campus"]')).not.toBeNull()
    const signal = mocks.fetch.mock.calls[0][1] as AbortSignal
    mocks.teamId = "team-b"
    view.rerender(<TenantCampusScene showControls />)
    expect(signal.aborted).toBe(true)
    expect(mocks.dispose).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(mocks.cesiumMount).toHaveBeenCalledTimes(2))
    expect(mocks.cesiumMount.mock.calls[1][1].teamId).toBe("team-b")
  })
  it("disposes the previous tenant and aborts its requests before mounting another", async () => {
    mocks.fetch.mockImplementation((id: string) => Promise.resolve(manifest(id)))
    const view = render(<TenantCampusScene showControls />)
    await waitFor(() => expect(mocks.mount).toHaveBeenCalledTimes(1))
    const signal = mocks.fetch.mock.calls[0][1] as AbortSignal
    mocks.teamId = "team-b"
    view.rerender(<TenantCampusScene showControls />)
    expect(signal.aborted).toBe(true)
    expect(mocks.dispose).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(mocks.mount).toHaveBeenCalledTimes(2))
    expect(mocks.mount.mock.calls[1][1].teamId).toBe("team-b")
    expect(view.container.querySelector('[data-team-id="team-a"]')).toBeNull()
  })
  it("never mounts a late response for the previous tenant", async () => {
    let resolveA: (data: unknown) => void = () => {}
    mocks.fetch.mockImplementation((id: string) => id === "team-a" ? new Promise((resolve) => { resolveA = resolve }) : Promise.resolve(manifest(id)))
    const view = render(<TenantCampusScene showControls />)
    mocks.teamId = "team-b"
    view.rerender(<TenantCampusScene showControls />)
    await waitFor(() => expect(mocks.mount).toHaveBeenCalledTimes(1))
    resolveA(manifest("team-a"))
    await waitFor(() => expect(view.container.querySelector('[data-scene-status="ready"]')).not.toBeNull())
    expect(mocks.mount.mock.calls.map((call) => call[1].teamId)).toEqual(["team-b"])
  })
  it("shows an unconfigured state without loading a default company's asset", async () => {
    mocks.fetch.mockRejectedValue(new SceneNotConfiguredError("当前租户尚未配置园区模型"))
    const view = render(<TenantCampusScene showControls />)
    await waitFor(() => expect(view.getByText("当前租户尚未配置园区模型")).toBeTruthy())
    expect(mocks.mount).not.toHaveBeenCalled()
    expect(mocks.fetch).toHaveBeenCalledTimes(1)
  })
})
