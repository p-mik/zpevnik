import { describe, expect, test } from 'vitest'
import { jmenoSouboruExportu, jsonExportu } from './akordyExport'

describe('jmenoSouboruExportu', () => {
  test('název písně a číslo verze', () => {
    expect(jmenoSouboruExportu('Raising my family', 2)).toBe('raising-my-family-verze-2.json')
  })

  test('diakritika se přepíše na ASCII, interpunkce na pomlčky', () => {
    expect(jmenoSouboruExportu('Přes Údolí! (živě)', 1)).toBe('pres-udoli-zive-verze-1.json')
  })

  test('pomlčky se neřetězí a nezůstávají na krajích', () => {
    expect(jmenoSouboruExportu('  ...Sloka -- Refrén...  ', 3)).toBe('sloka-refren-verze-3.json')
  })

  test('prázdný nebo nepoužitelný název dostane náhradu', () => {
    expect(jmenoSouboruExportu('', 1)).toBe('akordy-verze-1.json')
    expect(jmenoSouboruExportu('???', 1)).toBe('akordy-verze-1.json')
    expect(jmenoSouboruExportu(null, 1)).toBe('akordy-verze-1.json')
  })

  test('chybějící číslo verze se do názvu nepromítne', () => {
    expect(jmenoSouboruExportu('Africa', null)).toBe('africa.json')
    expect(jmenoSouboruExportu('Africa', 0)).toBe('africa.json')
  })

  test('dlouhý název se zkrátí a nekončí pomlčkou', () => {
    const jmeno = jmenoSouboruExportu('a'.repeat(80), 1)
    expect(jmeno).toBe(`${'a'.repeat(60)}-verze-1.json`)

    // Ořez přesně na hranici pomlčky nesmí nechat pomlčku na konci základu.
    const naHranici = jmenoSouboruExportu(`${'a'.repeat(60)} konec`, 1)
    expect(naHranici).toBe(`${'a'.repeat(60)}-verze-1.json`)
  })
})

describe('jsonExportu', () => {
  test('vrací přesně uložené schéma, odsazené a s koncovým newline', () => {
    const zapis = { schema: 2, takt: { dob: 4, hodnota: 4 }, tempo: null, sekce: [] }
    const text = jsonExportu(zapis)
    expect(text.endsWith('\n')).toBe(true)
    expect(JSON.parse(text)).toEqual(zapis)
    expect(text).toContain('\n  "schema": 2')
  })
})
