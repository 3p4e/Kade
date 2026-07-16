export default function StatusTag({ status }) {
  if (!status) return <span className="tag-pending">Pending</span>
  const cls = {
    PASS: 'tag-pass',
    FAIL: 'tag-fail',
    REVIEW: 'tag-review',
    PENDING: 'tag-pending',
  }[status] || 'tag-pending'
  return <span className={cls}>{status}</span>
}
