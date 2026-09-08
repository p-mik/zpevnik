import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import ProtectedLayout from './components/ProtectedLayout'
import LoginPage from './pages/LoginPage'
import SongListPage from './pages/SongListPage'
import SongDetailPage from './pages/SongDetailPage'
import FoldersPage from './pages/FoldersPage'
import SongbookPage from './pages/SongbookPage'
import SetlistsPlaceholderPage from './pages/SetlistsPlaceholderPage'
import PublicSongbookPage from './pages/PublicSongbookPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Veřejný zpěvník nesmí záviset na AuthProvideru fungovat — jen ho
            obaluje, aby appka měla jeden strom komponent; žádnou autentizaci
            nepoužívá. */}
        <Route path="/verejny/:token" element={<PublicSongbookPage />} />

        <Route path="/prihlaseni" element={<LoginPage />} />

        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Navigate to="/pisne" replace />} />
          <Route path="/pisne" element={<SongListPage />} />
          <Route path="/pisne/:id" element={<SongDetailPage />} />
          <Route path="/slozky" element={<FoldersPage />} />
          <Route path="/slozky/:id" element={<FoldersPage />} />
          <Route path="/zpevniky/:id" element={<SongbookPage />} />
          <Route path="/setlisty" element={<SetlistsPlaceholderPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthProvider>
  )
}
