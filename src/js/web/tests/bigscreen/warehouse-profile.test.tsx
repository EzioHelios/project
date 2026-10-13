import { act, cleanup, fireEvent, render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { SitePhoto, WarehouseGallery, WarehouseProfile } from "@/components/bigscreen/warehouse-profile"
import { useAuthStore } from "@/lib/auth"
import { getBigscreenPhoto } from "@/lib/bigscreen/api"
import type { BigscreenMediaItem } from "@/lib/bigscreen/types"
import type { Team } from "@/lib/generated/api"

const photos: BigscreenMediaItem[] = [{ id: "1", title: "立体库" }, { id: "2", title: "立体库" }, { id: "3", title: "充电区" }]
const query = vi.hoisted(() => ({ data: { data: { company_gallery: [] as BigscreenMediaItem[] } }, isError: false, refetch: vi.fn() }))
vi.mock("@/lib/bigscreen/hooks", () => ({ useBigscreenIntro: () => query }))
vi.mock("@/lib/bigscreen/api", () => ({ getBigscreenPhoto: vi.fn() }))
beforeEach(() => {
  useAuthStore.persist.setOptions({ storage: { getItem: () => null, setItem: () => {}, removeItem: () => {} } })
  useAuthStore.setState({ currentTeam: { id: "a", name: "祥泰仓库" } as Team })
  query.data.data.company_gallery = []
  query.isError = false
  vi.mocked(getBigscreenPhoto).mockResolvedValue(new Blob(["photo"], { type: "image/jpeg" }))
  URL.createObjectURL = vi.fn(() => "blob:photo")
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

it("shows facts without empty photo placeholders and resets the dialog on tenant switch", async () => {
  const view = render(<WarehouseProfile facts={[{ label: "登记设备", value: "9 台" }]} />)
  expect(view.queryByRole("img")).toBeNull()
  expect(view.container.textContent).not.toContain("暂无图片")
  fireEvent.click(view.getByRole("button", { name: "仓库概况" }))
  expect(view.getByRole("dialog")).toBeTruthy()
  await act(async () => useAuthStore.setState({ currentTeam: { id: "b", name: "安方中心库" } as Team }))
  expect(view.queryByRole("dialog")).toBeNull()
  expect(view.getByText("安方中心库")).toBeTruthy()
})

it("paginates authentic photos and resets selection when filtering regions", async () => {
  const view = render(<WarehouseGallery items={photos} />)
  await waitFor(() => expect(view.getByRole("img").getAttribute("alt")).toBe("立体库"))
  expect((view.getByRole("button", { name: "上一张" }) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(view.getByRole("button", { name: "下一张" }))
  expect(view.getByText("2 / 3")).toBeTruthy()
  fireEvent.change(view.getByLabelText("实景区域"), { target: { value: "充电区" } })
  expect(view.getByText("1 / 1")).toBeTruthy()
  await waitFor(() => expect(view.getByRole("img").getAttribute("alt")).toBe("充电区"))
  expect(vi.mocked(getBigscreenPhoto).mock.calls.at(-1)?.[1]?.teamId).toBe("a")
  view.unmount()
  expect(URL.revokeObjectURL).toHaveBeenCalled()
})

it("provides a retry for photo failures without substituting another warehouse", async () => {
  vi.mocked(getBigscreenPhoto).mockRejectedValueOnce(new Error("unavailable"))
  const view = render(<SitePhoto item={photos[0]} />)
  await waitFor(() => expect(view.getByRole("alert")).toBeTruthy())
  fireEvent.click(view.getByRole("button", { name: "重试照片" }))
  await waitFor(() => expect(view.getByRole("img")).toBeTruthy())
  expect(getBigscreenPhoto).toHaveBeenCalledTimes(2)
})
