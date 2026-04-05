import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import { SceneCard } from '../components/scenes/SceneCard'
import { useScenes } from '../hooks/useScenes'

export function ScenesPage() {
  const { scenes, loading, error, fetchScenes, createScene } = useScenes()
  const navigate = useNavigate()

  useEffect(() => {
    fetchScenes()
  }, [fetchScenes])

  const handleNewScene = async () => {
    const scene = await createScene({ title: 'Untitled Scene' })
    if (scene) navigate(`/scenes/${scene.id}`)
  }

  return (
    <div className="min-h-screen bg-bg">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-2xl font-bold text-text-primary">My Scenes</h2>
          <button
            onClick={handleNewScene}
            className="px-5 py-2.5 bg-primary text-white rounded-xl font-semibold hover:bg-primary-hover transition-colors"
          >
            + New Scene
          </button>
        </div>

        {loading && (
          <div className="flex justify-center py-20">
            <div className="animate-spin rounded-full h-10 w-10 border-4 border-accent border-t-transparent" />
          </div>
        )}

        {error && (
          <div className="text-center py-20 text-error">{error}</div>
        )}

        {!loading && !error && scenes.length === 0 && (
          <div className="text-center py-20 space-y-4">
            <span className="text-6xl block">🧱</span>
            <p className="text-text-secondary text-lg">No scenes yet. Build something and start your first movie!</p>
            <button
              onClick={handleNewScene}
              className="px-6 py-3 bg-accent text-black rounded-xl font-semibold hover:bg-accent-hover transition-colors"
            >
              Create Your First Scene
            </button>
          </div>
        )}

        {!loading && scenes.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {scenes.map(scene => (
              <SceneCard key={scene.id} scene={scene} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
