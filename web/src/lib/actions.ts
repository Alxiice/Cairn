import { api, desktop, type Version } from './api'
import { say } from './state.svelte'

/** Opens a version in Blender (desktop app, same machine as the server), else offers the download. */
export async function openInBlender(versionId: number) {
  try {
    const v = await api.get<Version>(`/versions/${versionId}`)
    const bridge = desktop()
    if (!bridge) {
      window.open(`/api/versions/${versionId}/file`, '_blank')
      say('Opening files in Blender needs the desktop app: the file was downloaded instead')
      return
    }
    const error = v.kind === 'blend' ? await bridge.open_in_blender(v.abs_path!) : await bridge.open_folder(v.abs_path!)
    say(error || (v.kind === 'blend' ? `Opening ${v.path.split('/').pop()} in Blender` : 'Folder opened'), !!error)
  } catch (e) {
    say(String(e), true)
  }
}

export async function openFolder(path: string) {
  const bridge = desktop()
  if (!bridge) return say(`Folder on the server: ${path}`)
  const error = await bridge.open_folder(path)
  if (error) say(error, true)
}

export async function uploadThumbnail(entityId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  try {
    await api.post(`/entities/${entityId}/thumbnail`, form)
    say('Thumbnail set')
  } catch (e) {
    say(String(e instanceof Error ? e.message : e), true)
  }
}
