import EmptyState from '../components/EmptyState'

// Nav odkaz na Setlisty je součástí potvrzené hlavičky, ale samotná
// obrazovka není v rozsahu tohohle tasku (API v /api/setlisty/ už existuje).
export default function SetlistsPlaceholderPage() {
  return (
    <EmptyState
      title="Setlisty se ještě staví"
      description="API pro setlisty už běží, obrazovka na to přijde v dalším kroku."
    />
  )
}
