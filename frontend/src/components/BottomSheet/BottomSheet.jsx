import { forwardRef } from 'react'
import './BottomSheet.css'

// 窄屏上的批注面板：不加遮罩，读者可以继续点其他词或段落。
const BottomSheet = forwardRef(function BottomSheet({ label, children }, ref) {
  return (
    <div ref={ref} className="sheet" role="region" aria-label={label}>
      <div className="sheet-handle" aria-hidden="true" />
      <div className="sheet-body">{children}</div>
    </div>
  )
})

export default BottomSheet
