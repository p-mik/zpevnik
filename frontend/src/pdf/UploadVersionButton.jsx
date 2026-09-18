import { useRef, useState } from 'react'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import './UploadVersionButton.css'

const CHYBA = 'Verzi se nepodařilo nahrát.'

// Nahrání vlastní (osobní) verze not přímo ze čtečky. Záchranná síť pro
// případ, že si někdo noty označí mimo appku — poznamená si je v čemkoliv,
// vyexportuje PDF a nahraje ho sem.
//
// Jde přes stejný endpoint a stejnou validaci jako každý jiný upload; `stav`
// se posílá výslovně, protože adminovi server nic nepředepisuje (viz
// VerzePisneViewSet.perform_create) a bez toho by vznikl obyčejný koncept.
export default function UploadVersionButton({ pisenId, onUploaded }) {
  const inputRef = useRef(null)
  const [nahravam, setNahravam] = useState(false)
  const [chyba, setChyba] = useState(null)

  async function zpracujVyber(e) {
    const soubor = e.target.files?.[0]
    // Vynulovat hned: jinak by druhý pokus s TÍMŽ souborem nevyvolal change.
    e.target.value = ''
    if (!soubor) return

    setNahravam(true)
    setChyba(null)
    try {
      const formData = new FormData()
      formData.append('pisen', String(pisenId))
      formData.append('soubor', soubor)
      formData.append('stav', 'personal')
      formData.append('typ_obsahu', 'pdf')
      const verze = await api.post('/api/verze-pisni/', formData, { isFormData: true })
      onUploaded(verze.id)
    } catch (err) {
      setChyba(extractErrorMessage(err, CHYBA))
    } finally {
      setNahravam(false)
    }
  }

  return (
    <div className="upload-version">
      <button
        type="button"
        className="btn btn-secondary upload-version-btn"
        onClick={() => inputRef.current?.click()}
        disabled={nahravam}
      >
        {nahravam ? 'Nahrávám…' : 'Nahrát vlastní verzi'}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="upload-version-input"
        onChange={zpracujVyber}
        aria-label="Vybrat PDF s vlastní verzí not"
      />
      {chyba && (
        <p className="upload-version-error" role="alert">
          {chyba}
        </p>
      )}
    </div>
  )
}
