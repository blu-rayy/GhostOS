import { useState } from 'react'

/** Open/acknowledge state for the two-step approval dialog. */
export function useApprovalState() {
  const [open, setOpen] = useState(false)
  const [ack, setAck] = useState(false)
  return {
    open,
    ack,
    setAck,
    show: () => {
      setAck(false)
      setOpen(true)
    },
    hide: () => setOpen(false),
  }
}
