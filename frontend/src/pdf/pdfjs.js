// Jedno místo, kde se PDF.js nastavuje — worker se natáhne jako lokální
// bundlovaný soubor (Vite `?url`), nikdy z CDN/unpkg.
import * as pdfjsLib from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc

export default pdfjsLib
