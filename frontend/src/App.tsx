import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RequireAuth, RedirectIfAuthed } from './components/guards'
import { Layout } from './components/Layout'
import { LoginPage } from './pages/Login'
import { RegisterPage } from './pages/Register'
import { NotesListPage } from './pages/NotesList'
import { NoteDetailPage } from './pages/NoteDetail'
import { UploadPage } from './pages/Upload'
import { MyUploadsPage } from './pages/MyUploads'
import { WalletPage } from './pages/Wallet'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Auth/session state is managed manually; server data refetches on
      // window focus are more noise than value for this app.
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              <RedirectIfAuthed>
                <LoginPage />
              </RedirectIfAuthed>
            }
          />
          <Route
            path="/register"
            element={
              <RedirectIfAuthed>
                <RegisterPage />
              </RedirectIfAuthed>
            }
          />
          {/* All app routes sit behind the auth guard, inside the nav layout. */}
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<NotesListPage />} />
            <Route path="/notes/:noteId" element={<NoteDetailPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/my" element={<MyUploadsPage />} />
            <Route path="/wallet" element={<WalletPage />} />
          </Route>
          <Route path="*" element={<NotesListPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
