/** One `### Task N: Title` section of a plan; line bounds are 1-based and inclusive. */
export type PlanTask = {
  number: number
  title: string
  startLine: number
  endLine: number
  verification: string[]
}

const HEADING = /^###\s+Task\s+(\d+)\s*:\s*(.+?)\s*$/
const FENCE = /^\s*(```|~~~)/
const VERIFICATION = /^\*\*Verification:?\*\*:?\s*$/
const COMMAND = /^\s*-\s+`([^`]+)`/

/** Reads the plan template's task sections; a plan without `### Task N:` headings yields `[]`. */
export function parsePlan(text: string): PlanTask[] {
  const lines = text.split('\n')
  const tasks: PlanTask[] = []
  let current: PlanTask | undefined
  let inFence = false
  let inVerification = false

  lines.forEach((line, i) => {
    const n = i + 1
    if (FENCE.test(line)) inFence = !inFence
    if (inFence) return
    const heading = HEADING.exec(line)
    if (heading && !tasks.some(t => t.number === Number(heading[1]))) {
      if (current) current.endLine = n - 1
      current = { number: Number(heading[1]), title: heading[2]!, startLine: n, endLine: lines.length, verification: [] }
      tasks.push(current)
      inVerification = false
      return
    }
    if (/^##\s/.test(line) && current) { current.endLine = n - 1; current = undefined; return }
    if (!current) return
    if (VERIFICATION.test(line)) { inVerification = true; return }
    if (inVerification) {
      const cmd = COMMAND.exec(line)
      if (cmd) current.verification.push(cmd[1]!)
      else if (line.trim() !== '' && !/^\s+/.test(line)) inVerification = false
    }
  })
  return tasks
}
