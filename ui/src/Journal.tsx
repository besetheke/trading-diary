import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  aendereNotiz,
  ersetzeTags,
  fehlerText,
  holeAlleSchlagwoerter,
  holeJournal,
  legeNotizAn,
  loescheNotiz,
} from './api'
import type { JournalInhalt, Notiz, Schlagwort } from './api'
import { zeit, zeitDe } from './format'

// AP-08j, Punkt 2: Der Journal-Baustein — Notizen und Tags zu einem Bereich
// (chain, structure, campaign, tag). Die Oberfläche bleibt dünn: Reihenfolge
// und Inhalt kommen von der API; hier wird nur angezeigt, gesendet und nach
// jeder Änderung neu gelesen. Der Text bleibt unverändert, Leerraum
// inklusive — nur eine Notiz ohne sichtbaren Text wird gar nicht gesendet.

interface Bearbeitung {
  id: number
  text: string
}

export default function Journal({
  scopeTyp,
  scopeId,
}: {
  scopeTyp: string
  scopeId: string
}): JSX.Element {
  const [inhalt, setzeInhalt] = useState<JournalInhalt | null>(null)
  const [vorschlaege, setzeVorschlaege] = useState<Schlagwort[]>([])
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [neuText, setzeNeuText] = useState('')
  const [bearbeitung, setzeBearbeitung] = useState<Bearbeitung | null>(null)
  // null heißt: Tags werden nur gezeigt; eine Zeichenkette heißt: Bearbeiten.
  const [tagEntwurf, setzeTagEntwurf] = useState<string | null>(null)
  const [beschaeftigt, setzeBeschaeftigt] = useState(false)

  useEffect(() => {
    let abgebrochen = false
    setzeInhalt(null)
    setzeFehler(null)
    setzeBearbeitung(null)
    setzeTagEntwurf(null)
    holeJournal(scopeTyp, scopeId)
      .then((ergebnis) => {
        if (!abgebrochen) setzeInhalt(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [scopeTyp, scopeId])

  // Vorschläge für die Tag-Eingabe: einmal je Baustein — GET /tags ändert sich
  // nur mit den Zuordnungen, und die werden nach jeder Aktion neu gelesen.
  useEffect(() => {
    let abgebrochen = false
    holeAlleSchlagwoerter()
      .then((ergebnis) => {
        if (!abgebrochen) setzeVorschlaege(ergebnis)
      })
      .catch(() => {
        /* Ohne Vorschläge bleibt die Eingabe frei — kein Fehlergrund. */
      })
    return () => {
      abgebrochen = true
    }
  }, [])

  // Nach jeder Schreibaktion Journal und Vorschläge gemeinsam neu lesen —
  // die API ist die einzige Quelle, die Oberfläche hält nichts zurück.
  function neuLaden(): Promise<void> {
    return Promise.all([holeJournal(scopeTyp, scopeId), holeAlleSchlagwoerter()]).then(
      ([journal, schlagwoerter]) => {
        setzeInhalt(journal)
        setzeVorschlaege(schlagwoerter)
        setzeBearbeitung(null)
        setzeTagEntwurf(null)
      },
    )
  }

  function fehlFang(ursache: unknown): void {
    setzeFehler(fehlerText(ursache))
    setzeBeschaeftigt(false)
  }

  function notizAnlegen(ereignis: FormEvent): void {
    ereignis.preventDefault()
    // Leere Notizen werden nicht gesendet — der Text selbst bleibt unverändert.
    if (neuText.trim() === '') return
    setzeBeschaeftigt(true)
    setzeFehler(null)
    legeNotizAn(scopeTyp, scopeId, neuText)
      .then(() => {
        setzeNeuText('')
        return neuLaden()
      })
      .then(() => setzeBeschaeftigt(false))
      .catch(fehlFang)
  }

  function aenderungSpeichern(ereignis: FormEvent): void {
    ereignis.preventDefault()
    if (bearbeitung === null || bearbeitung.text.trim() === '') return
    setzeBeschaeftigt(true)
    setzeFehler(null)
    aendereNotiz(bearbeitung.id, bearbeitung.text)
      .then(neuLaden)
      .then(() => setzeBeschaeftigt(false))
      .catch(fehlFang)
  }

  function notizLoeschen(notiz: Notiz): void {
    if (!window.confirm(`Diese Notiz vom ${zeitDe(notiz.erstellt_am)} löschen?`)) return
    setzeBeschaeftigt(true)
    setzeFehler(null)
    loescheNotiz(notiz.id)
      .then(neuLaden)
      .then(() => setzeBeschaeftigt(false))
      .catch(fehlFang)
  }

  function tagsSpeichern(ereignis: FormEvent): void {
    ereignis.preventDefault()
    if (tagEntwurf === null) return
    const namen = tagEntwurf
      .split(',')
      .map((name) => name.trim())
      .filter((name) => name !== '')
    setzeBeschaeftigt(true)
    setzeFehler(null)
    ersetzeTags(scopeTyp, scopeId, namen)
      .then(neuLaden)
      .then(() => setzeBeschaeftigt(false))
      .catch(fehlFang)
  }

  return (
    <section className="journal">
      <h3>Journal</h3>
      {fehler && <p className="meldung">{fehler}</p>}

      {inhalt === null && !fehler && <p className="laedt">Lade Journal …</p>}

      {inhalt !== null && (
        <>
          <h4>Tags</h4>
          {tagEntwurf === null ? (
            <div className="zeile">
              {inhalt.tags.length === 0 ? (
                <p className="leer">Noch keine Tags.</p>
              ) : (
                <ul className="schlagwoerter">
                  {inhalt.tags.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                disabled={beschaeftigt}
                onClick={() => setzeTagEntwurf(inhalt.tags.join(', '))}
              >
                Tags bearbeiten
              </button>
            </div>
          ) : (
            <form onSubmit={tagsSpeichern}>
              <label htmlFor={`tags-${scopeTyp}-${scopeId}`}>
                Tags, durch Komma getrennt — Speichern ersetzt die Zuordnung
              </label>
              <input
                id={`tags-${scopeTyp}-${scopeId}`}
                list={`vorschlaege-${scopeTyp}-${scopeId}`}
                value={tagEntwurf}
                onChange={(ereignis) => setzeTagEntwurf(ereignis.target.value)}
              />
              <datalist id={`vorschlaege-${scopeTyp}-${scopeId}`}>
                {vorschlaege.map((schlagwort) => (
                  <option key={schlagwort.name} value={schlagwort.name} />
                ))}
              </datalist>
              <button type="submit" disabled={beschaeftigt}>
                Speichern
              </button>
              <button type="button" disabled={beschaeftigt} onClick={() => setzeTagEntwurf(null)}>
                Abbrechen
              </button>
            </form>
          )}

          <h4>Notizen</h4>
          {inhalt.notizen.length === 0 && <p className="leer">Noch keine Notizen.</p>}
          <ul className="notizen">
            {inhalt.notizen.map((notiz) => (
              <li key={notiz.id}>
                {bearbeitung?.id === notiz.id ? (
                  <form onSubmit={aenderungSpeichern}>
                    <textarea
                      value={bearbeitung.text}
                      onChange={(ereignis) =>
                        setzeBearbeitung({ id: notiz.id, text: ereignis.target.value })
                      }
                    />
                    <div className="zeile">
                      <button type="submit" disabled={beschaeftigt}>
                        Speichern
                      </button>
                      <button
                        type="button"
                        disabled={beschaeftigt}
                        onClick={() => setzeBearbeitung(null)}
                      >
                        Abbrechen
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <p
                      className="zeitstempel"
                      title={`${zeit(notiz.erstellt_am)}${
                        notiz.geaendert_am ? ` · geändert ${zeit(notiz.geaendert_am)}` : ''
                      }`}
                    >
                      {zeitDe(notiz.erstellt_am)}
                      {notiz.geaendert_am ? ` · geändert ${zeitDe(notiz.geaendert_am)}` : ''}
                    </p>
                    <p className="notiztext">{notiz.text}</p>
                    <div className="zeile">
                      <button
                        type="button"
                        disabled={beschaeftigt}
                        onClick={() => setzeBearbeitung({ id: notiz.id, text: notiz.text })}
                      >
                        Bearbeiten
                      </button>
                      <button
                        type="button"
                        disabled={beschaeftigt}
                        onClick={() => notizLoeschen(notiz)}
                      >
                        Löschen
                      </button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>

          <form onSubmit={notizAnlegen}>
            <label htmlFor={`notiz-${scopeTyp}-${scopeId}`}>Neue Notiz</label>
            <textarea
              id={`notiz-${scopeTyp}-${scopeId}`}
              value={neuText}
              placeholder="Was war bemerkenswert?"
              onChange={(ereignis) => setzeNeuText(ereignis.target.value)}
            />
            <div className="zeile">
              <button type="submit" disabled={beschaeftigt || neuText.trim() === ''}>
                Notiz speichern
              </button>
            </div>
          </form>
        </>
      )}
    </section>
  )
}
