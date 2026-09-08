import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import ProtectedLayout from './components/ProtectedLayout'
import LoadingState from './components/LoadingState'
import LoginPage from './pages/LoginPage'
import SongListPage from './pages/SongListPage'
import SongDetailPage from './pages/SongDetailPage'
import FoldersPage from './pages/FoldersPage'
import SongbookPage from './pages/SongbookPage'
import SetlistsPlaceholderPage from './pages/SetlistsPlaceholderPage'
import PublicSongbookPage from './pages/PublicSongbookPage'
import NotFoundPage from './pages/NotFoundPage'

// PDF.js je těžká knihovna (~500 kB) — čtečka a stage mode se natáhnou, jen
// když je uživatel opravdu otevře, ne při každém načtení appky.
const SongReaderPage = lazy(() => import('./pages/SongReaderPage'))
const StageModePage = lazy(() => import('./pages/StageModePage'))
const PublicSongReaderPage = lazy(() => import('./pages/PublicSongReaderPage'))
const PublicStageModePage = lazy(() => import('./pages/PublicStageModePage'))

export default function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<LoadingState label="Načítám čtečku…" />}>
        <Routes>
          {/* Veřejný zpěvník nesmí záviset na AuthProvideru fungovat — jen ho
              obaluje, aby appka měla jeden strom komponent; žádnou autentizaci
              nepoužívá. */}
          <Route path="/verejny/:token" element={<PublicSongbookPage />} />
          <Route path="/verejny/:token/pisen/:kod" element={<PublicSongReaderPage />} />
          <Route path="/verejny/:token/pisen/:kod/stage" element={<PublicStageModePage />} />

          <Route path="/prihlaseni" element={<LoginPage />} />

          {/* Čtečka a stage mode nejsou v ProtectedLayoutu schválně — mají
              vlastní, jemnější bránu (useReaderAuth), která uprostřed čtení
              při vypršelé session obsah nesmaže, jen upozorní (viz zadání
              fáze 1d). ProtectedLayout by tu při ztrátě session okamžitě
              přesměroval na přihlášení a rozečtené noty zmizely beze stopy. */}
          <Route path="/pisne/:id/ctecka" element={<SongReaderPage />} />
          <Route path="/pisne/:id/stage" element={<StageModePage />} />

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
      </Suspense>
    </AuthProvider>
  )
}
