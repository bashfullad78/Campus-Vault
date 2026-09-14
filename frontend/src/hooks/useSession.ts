import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe } from '../api/auth'
import { refreshSession, getRefreshToken, clearTokens } from '../api/client'
import type { UserOut } from '../api/types'

/**
 * ['me'] — the authenticated user cache. Null means "not signed in".
 *
 * Session restore (frontend.txt §4.6): if a refresh token exists, refresh
 * FIRST, then /auth/me. Protected routes wait on this query before rendering,
 * so a page never mounts twice or flashes an error during restore.
 */
export function useSession() {
  const hasRefreshToken = Boolean(getRefreshToken())

  const query = useQuery<UserOut | null>({
    queryKey: ['me'],
    // No refetch loops: auth state only changes through explicit mutations.
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
    queryFn: async () => {
      if (!getRefreshToken()) return null
      // Restore path: silent refresh first (rotates the token pair), then me.
      const renewed = await refreshSession()
      if (!renewed) {
        clearTokens()
        return null
      }
      return fetchMe()
    },
    enabled: hasRefreshToken || undefined,
  })

  const queryClient = useQueryClient()

  const setSession = (user: UserOut | null) => {
    queryClient.setQueryData(['me'], user)
  }

  return {
    user: query.data ?? null,
    loading: hasRefreshToken && query.isLoading,
    setSession,
  }
}
