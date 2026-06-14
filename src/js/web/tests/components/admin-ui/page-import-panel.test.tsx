import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PageImportPanel } from "@/components/admin-ui"
import { scope2BillImportFields } from "@/components/carbon/page-import-configs"

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe("PageImportPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("downloads a Chinese template", async () => {
    const createObjectURL = vi.fn(() => "blob:page-import-template")
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL })
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)

    render(<PageImportPanel title="账单导入" fields={scope2BillImportFields} testId="scope2-import" onConfirm={vi.fn()} />)

    await userEvent.click(screen.getByTestId("scope2-import-trigger"))
    await userEvent.click(screen.getByTestId("scope2-import-template-download"))

    const blob = createObjectURL.mock.calls[0]?.[0] as Blob
    const templateText = await readBlobText(blob)
    expect(templateText).toContain("来源记录ID")
    expect(templateText).toContain("总电量(kWh)")
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:page-import-template")
  })

  it("uploads a CSV file, maps Chinese headers to English fields, and shows the result summary", async () => {
    const onConfirm = vi.fn(async () => ({ receivedCount: 1, importedCount: 1, skippedCount: 0, errors: [] }))
    const user = userEvent.setup()
    render(<PageImportPanel title="账单导入" fields={scope2BillImportFields} testId="scope2-import" onConfirm={onConfirm} />)

    await user.click(screen.getByTestId("scope2-import-trigger"))
    const csv = "来源记录ID,户号,账期,总电量(kWh),金额(元)\nbill-1,32000001,2026-03,12800,9800\n"
    await user.upload(screen.getByTestId("scope2-import-file"), new File([csv], "scope2.csv", { type: "text/csv" }))
    await user.click(screen.getByTestId("scope2-import-submit"))

    await waitFor(() =>
      expect(onConfirm).toHaveBeenCalledWith(
        [
          {
            source_record_id: "bill-1",
            account_number: "32000001",
            billing_month: "2026-03",
            total_kwh: "12800",
            amount_cny: "9800",
          },
        ],
        { sourceName: "页面级导入" },
      ),
    )
    expect(screen.getByText("服务端入库")).toBeInTheDocument()
    expect(screen.getAllByText("1").length).toBeGreaterThan(0)
  })

  it("blocks confirmation and downloads errors when required or numeric fields fail validation", async () => {
    const createObjectURL = vi.fn(() => "blob:page-import-errors")
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL })
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(<PageImportPanel title="账单导入" fields={scope2BillImportFields} testId="scope2-import" onConfirm={onConfirm} />)

    await user.click(screen.getByTestId("scope2-import-trigger"))
    const csv = "来源记录ID,户号,账期,总电量(kWh)\nbill-1,,2026-03,abc\n"
    await user.upload(screen.getByTestId("scope2-import-file"), new File([csv], "scope2.csv", { type: "text/csv" }))

    expect(await screen.findByText("户号不能为空")).toBeInTheDocument()
    expect(screen.getByText("总电量(kWh)必须是数字")).toBeInTheDocument()
    expect(screen.getByTestId("scope2-import-submit")).toBeDisabled()
    expect(onConfirm).not.toHaveBeenCalled()

    await user.click(screen.getByTestId("scope2-import-errors-download"))
    const blob = createObjectURL.mock.calls[0]?.[0] as Blob
    const errorText = await readBlobText(blob)
    expect(errorText).toContain("户号不能为空")
    expect(errorText).toContain("总电量(kWh)必须是数字")
    expect(errorText).toContain("bill-1,,2026-03,abc")
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:page-import-errors")
  })
})

function readBlobText(blob: Blob) {
  if (typeof blob.text === "function") return blob.text()
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ""))
    reader.onerror = () => reject(reader.error ?? new Error("Blob 读取失败"))
    reader.readAsText(blob)
  })
}
