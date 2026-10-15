/** Photos taken or picked on a phone are often 3–10 MB; send a JPEG at most 1600 px wide instead. */
import { readFile } from './ops'

const MAX_INPUT_MB = 25

function decode(file) {
  if (window.createImageBitmap) return createImageBitmap(file, { imageOrientation: 'from-image' })
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = URL.createObjectURL(file)
  })
}

const toBase64 = (blob) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = () => reject(new Error('Could not read the photo.'))
    reader.readAsDataURL(blob)
  })

/** { content: base64 JPEG, preview: object URL } for a picked or captured photo. */
export async function shrink(file, max = 1600, quality = 0.82) {
  if (!file?.type?.startsWith('image/')) throw new Error('Choose a photo.')
  if (file.size > MAX_INPUT_MB * 1024 * 1024) throw new Error(`Choose a photo smaller than ${MAX_INPUT_MB} MB.`)
  try {
    const image = await decode(file)
    const width = image.width || image.naturalWidth
    const height = image.height || image.naturalHeight
    const scale = Math.min(1, max / Math.max(width, height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(width * scale)
    canvas.height = Math.round(height * scale)
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height)
    image.close?.()
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    if (!blob) throw new Error('encode')
    return { content: await toBase64(blob), preview: URL.createObjectURL(blob) }
  } catch (e) {
    // A format this browser cannot draw: send the original if the server accepts it (JPEG or PNG, 10 MB).
    if (!/^image\/(jpeg|png)$/.test(file.type)) throw new Error('This photo format is not supported. Choose a JPEG or PNG photo.')
    return { content: await readFile(file), preview: URL.createObjectURL(file) }
  }
}

/** Phones and tablets open their own camera app from a file input; computers need the webcam window. */
export const touchDevice = () => typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches
