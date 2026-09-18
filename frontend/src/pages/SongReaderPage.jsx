import { useEffect, useState } from 'react'
import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useReaderAuth } from '../pdf/useReaderAuth'
import { resolveVerze } from '../pdf/resolveVerze'
import { useSongNavigation } from '../pdf/useSongNavigation'
import { useAnotace, useVarovaniPriOdchodu } from '../pdf/useAnotace'
import { novaAnotace } from '../pdf/anotaceModel'
import ReaderView from '../pdf/ReaderView'
import VersionSwitcher from '../pdf/VersionSwitcher'
import UploadVersionButton from '../pdf/UploadVersionButton'
import AnnotationLayer from '../pdf/AnnotationLayer'
import AnnotationToolbar from '../pdf/AnnotationToolbar'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'

export default function SongReaderPage() {
  const auth = useReaderAuth()
  const { id } = useParams()
  const [searchParams] = useSearchParams()

  const { data: song, loading, error, reload } = useApiResource(
    auth.status === 'ready' ? `/api/pisne/${id}/` : null,
  )

  if (auth.status === 'loading') return <LoadingState label="Ověřuji přihlášení…" />
  if (auth.status === 'redirect') {
    return <Navigate to="/prihlaseni" replace state={{ from: auth.from }} />
  }

  if (loading) return <LoadingState label="Načítám píseň…" />
  if (error) {
    return (
      <ErrorState
        message={error.status === 404 ? 'Tahle píseň neexistuje.' : 'Píseň se nepodařilo načíst.'}
        onRetry={error.status === 404 ? undefined : reload}
      />
    )
  }

  // Vlastní čtečka je zvlášť, protože pracuje s hooky (anotace), které by nad
  // ještě nenačtenou písní nešlo volat bez podmínky.
  return (
    <CtenaPisen
      key={song.id}
      song={song}
      reload={reload}
      sessionLost={auth.sessionLost}
      pozadovanaVerze={Number(searchParams.get('verze'))}
    />
  )
}

function CtenaPisen({ song, reload, sessionLost, pozadovanaVerze }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const zpevnikId = searchParams.get('z')
  const { prevSong, nextSong } = useSongNavigation(String(song.id), zpevnikId)
  const { currentVerze, unavailableTitle, unavailableMessage } = resolveVerze(
    song,
    pozadovanaVerze,
  )

  const [rezimUprav, setRezimUprav] = useState(false)
  const [vybranyId, setVybranyId] = useState(null)
  // "Nástroj" pro vkládání — styl, který dostane příští nové pole. Přepnutí
  // platí, dokud ho uživatel nezmění, ať psaní víc akordů/značek za sebou
  // nevyžaduje po každém dvojkliku znovu sahat na lištu.
  const [typProNove, setTypProNove] = useState('normal')
  const anotace = useAnotace(currentVerze?.id)
  useVarovaniPriOdchodu(anotace.zmeneno)

  // Poznámky patří ke konkrétní verzi — po přepnutí verze se načtou jiné a
  // výběr z té předchozí by ukazoval na neexistující pole.
  useEffect(() => {
    setVybranyId(null)
  }, [currentVerze?.id])

  const zSuffix = zpevnikId ? `?z=${zpevnikId}` : ''
  const vybrany = anotace.objekty.find((o) => o.id === vybranyId) || null

  function prepniNaVerzi(verzeId) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('verze', String(verzeId))
      return next
    })
  }

  // Klik na typ v liště vždy nastaví "nástroj" pro příští vložení a navíc,
  // pokud je zrovna něco vybrané, rovnou přebarví i to pole.
  function nastavStyl(styl) {
    setTypProNove(styl)
    if (vybrany) anotace.zmen(vybrany.id, { styl })
  }

  return (
    <ReaderView
      pdfPath={currentVerze ? `/api/verze-pisni/${currentVerze.id}/soubor/` : null}
      unavailableTitle={unavailableTitle}
      unavailableMessage={unavailableMessage}
      backHref={`/pisne/${song.id}`}
      backLabel="Zpět na píseň"
      codeLabel={String(song.kod).padStart(3, '0')}
      title={song.nazev}
      subtitle={song.interpret}
      sessionBanner={sessionLost}
      versionSwitcher={
        <VersionSwitcher verze={song.verze} currentId={currentVerze?.id} onChange={prepniNaVerzi} />
      }
      uploadButton={
        <UploadVersionButton
          pisenId={song.id}
          onUploaded={(verzeId) => {
            // Pořadí: nejdřív URL, pak načtení písně — přepínač verzí novou
            // položku uvidí až po reloadu a rovnou ji ukáže jako vybranou.
            prepniNaVerzi(verzeId)
            reload()
          }}
        />
      }
      annotationToggle={
        currentVerze && !unavailableMessage ? (
          <button
            type="button"
            className={`btn btn-secondary reader-anotace-prepinac${rezimUprav ? ' reader-anotace-aktivni' : ''}`}
            onClick={() => setRezimUprav((v) => !v)}
            aria-pressed={rezimUprav}
          >
            Poznámky
            {anotace.objekty.length > 0 && ` (${anotace.objekty.length})`}
          </button>
        ) : null
      }
      annotationBar={
        rezimUprav ? (
          <AnnotationToolbar
            vybrany={vybrany}
            typProNove={typProNove}
            onStyl={nastavStyl}
            onVelikost={(velikost) => vybrany && anotace.zmen(vybrany.id, { velikost })}
            onText={(text) => vybrany && anotace.zmen(vybrany.id, { text })}
            onSmazat={() => {
              if (!vybrany) return
              anotace.smaz(vybrany.id)
              setVybranyId(null)
            }}
            onKonec={() => setRezimUprav(false)}
            onUlozit={anotace.uloz}
            zmeneno={anotace.zmeneno}
            ukladam={anotace.ukladam}
            chyba={anotace.chyba}
          />
        ) : null
      }
      renderOverlay={(strana) => (
        <AnnotationLayer
          objekty={anotace.objekty.filter((o) => o.strana === strana)}
          varianta="app"
          editovatelne={rezimUprav}
          vybranyId={vybranyId}
          onVybrat={setVybranyId}
          onVytvorit={(x, y) => {
            const objekt = novaAnotace(strana, x, y, typProNove)
            anotace.pridej(objekt)
            setVybranyId(objekt.id)
            // Návratová hodnota: AnnotationLayer podle ní rovnou otevře
            // editaci textu nového pole, bez druhého dvojkliku navíc.
            return objekt.id
          }}
          onZmenit={anotace.zmen}
          onSmazat={(id) => {
            anotace.smaz(id)
            setVybranyId(null)
          }}
        />
      )}
      stageHref={
        currentVerze
          ? `/pisne/${song.id}/stage?verze=${currentVerze.id}${zpevnikId ? `&z=${zpevnikId}` : ''}`
          : undefined
      }
      prevSongHref={prevSong ? `/pisne/${prevSong.id}/ctecka${zSuffix}` : undefined}
      nextSongHref={nextSong ? `/pisne/${nextSong.id}/ctecka${zSuffix}` : undefined}
      pickerHrefFor={(pisen) => `/pisne/${pisen.id}/ctecka${zSuffix}`}
      currentSongId={song.id}
    />
  )
}
