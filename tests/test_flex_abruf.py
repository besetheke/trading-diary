"""Abnahmetests für AP-02a2: automatischer Abruf der Flex-Query über den
Flex Web Service (`ingest/flex_abruf.py`, `journal abrufen`).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-02a2.md`.

Es wird **nie** das Netz berührt: Der Abruf nimmt einen Transport entgegen
(`transport(url) -> bytes`), die Tests reichen einen erfundenen. Antworten
im Format des Flex Web Service (Version 3):

  SendRequest -> <FlexStatementResponse><Status>Success</Status>
                 <ReferenceCode>…</ReferenceCode><Url>…</Url>
  GetStatement -> das Statement (<FlexQueryResponse>) oder, solange es
                 erzeugt wird, <Status>Warn</Status><ErrorCode>1019</ErrorCode>
  Fehler        -> <Status>Fail</Status><ErrorCode>…</ErrorCode>
                 <ErrorMessage>…</ErrorMessage>

Der Token ist ein Geheimnis: Er darf in keiner Fehlermeldung, Ausgabe oder
Datei auftauchen.
"""

import pathlib
import re

import pytest
from sqlalchemy import func, select

from ingest import flex_abruf
from ingest.flex_abruf import AbrufFehler, abrufen, statement_speichern
from journal.cli import main
from journal.db import create_db_engine
from journal.schema import executions

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "flex"
STATEMENT = (FIXTURES / "activity_2026_01.xml").read_bytes()
TOKEN = "GEHEIM4711"
QUERY = "246810"
URL_GETSTATEMENT = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement"

SEND_OK = (
    '<FlexStatementResponse timestamp="09 October, 2026 08:00 PM EDT">'
    "<Status>Success</Status><ReferenceCode>1234567890</ReferenceCode>"
    f"<Url>{URL_GETSTATEMENT}</Url></FlexStatementResponse>"
).encode()
IN_ARBEIT = (
    b'<FlexStatementResponse timestamp="09 October, 2026 08:00 PM EDT">'
    b"<Status>Warn</Status><ErrorCode>1019</ErrorCode>"
    b"<ErrorMessage>Statement generation in progress. Please try again shortly.</ErrorMessage>"
    b"</FlexStatementResponse>"
)


def _fehler(code: str, text: str) -> bytes:
    return (
        '<FlexStatementResponse timestamp="09 October, 2026 08:00 PM EDT">'
        f"<Status>Fail</Status><ErrorCode>{code}</ErrorCode>"
        f"<ErrorMessage>{text}</ErrorMessage></FlexStatementResponse>"
    ).encode()


class Transport:
    """Erfundener Transport: liefert die Antworten der Reihe nach."""

    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        antwort = self.antworten.pop(0)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort


class Uhr:
    """Zeichnet die Wartezeiten auf, statt zu warten."""

    def __init__(self):
        self.pausen: list[float] = []

    def __call__(self, sekunden: float) -> None:
        self.pausen.append(sekunden)


# ---------------------------------------------------------------- Abruf


def test_abruf_zwei_schritte_und_urls():
    transport, uhr = Transport(SEND_OK, STATEMENT), Uhr()

    ergebnis = abrufen(TOKEN, QUERY, transport=transport, warten=uhr)

    assert ergebnis == STATEMENT
    assert uhr.pausen == []
    erste, zweite = transport.urls
    assert "SendRequest" in erste
    assert f"t={TOKEN}" in erste and f"q={QUERY}" in erste and "v=3" in erste
    # Schritt 2: die Url aus der Antwort, mit dem ReferenceCode - nicht der Query-ID.
    assert zweite.startswith(URL_GETSTATEMENT)
    assert f"t={TOKEN}" in zweite and "q=1234567890" in zweite and "v=3" in zweite
    assert f"q={QUERY}" not in zweite


def test_statement_in_arbeit_wird_wiederholt():
    transport, uhr = Transport(SEND_OK, IN_ARBEIT, IN_ARBEIT, STATEMENT), Uhr()

    ergebnis = abrufen(TOKEN, QUERY, transport=transport, warten=uhr, wartezeit_s=5.0)

    assert ergebnis == STATEMENT
    assert uhr.pausen == [5.0, 5.0]
    assert len(transport.urls) == 4


def test_zu_viele_versuche_brechen_ab():
    transport, uhr = Transport(SEND_OK, IN_ARBEIT, IN_ARBEIT, IN_ARBEIT), Uhr()

    with pytest.raises(AbrufFehler, match="nicht rechtzeitig"):
        abrufen(TOKEN, QUERY, transport=transport, warten=uhr, wartezeit_s=5.0, max_versuche=3)

    # Drei Versuche, zwischen ihnen zweimal gewartet; nie unbegrenzt.
    assert len(transport.urls) == 4  # 1 SendRequest + 3 GetStatement
    assert uhr.pausen == [5.0, 5.0]


def test_fehler_der_gegenstelle_nennt_code_und_text_aber_nie_den_token():
    transport = Transport(_fehler("1015", "Token is invalid."))

    with pytest.raises(AbrufFehler) as fehler:
        abrufen(TOKEN, QUERY, transport=transport, warten=Uhr())

    text = str(fehler.value)
    assert "1015" in text and "Token is invalid." in text
    assert TOKEN not in text
    assert len(transport.urls) == 1


def test_fehler_beim_holen_ist_endgueltig_und_wird_nicht_wiederholt():
    transport, uhr = Transport(SEND_OK, _fehler("1012", "Token has expired.")), Uhr()

    with pytest.raises(AbrufFehler, match="1012"):
        abrufen(TOKEN, QUERY, transport=transport, warten=uhr)

    assert len(transport.urls) == 2
    assert uhr.pausen == []


@pytest.mark.parametrize("antwort", [b"<html>Gateway Timeout</html>", b"\x00\x01 kein xml", b""])
def test_unbekannte_antwort_beim_senden(antwort):
    with pytest.raises(AbrufFehler, match="unbekannte Antwort") as fehler:
        abrufen(TOKEN, QUERY, transport=Transport(antwort), warten=Uhr())

    assert "Gateway" not in str(fehler.value)  # der Körper wird nicht ausgegeben


def test_unbekannte_antwort_beim_holen():
    with pytest.raises(AbrufFehler, match="unbekannte Antwort"):
        abrufen(TOKEN, QUERY, transport=Transport(SEND_OK, b"<Etwas Anderes/>"), warten=Uhr())


def test_transportfehler_werden_zu_abruffehlern_ohne_token():
    fremd = OSError(f"connection refused https://x/SendRequest?t={TOKEN}&q={QUERY}")

    with pytest.raises(AbrufFehler) as fehler:
        abrufen(TOKEN, QUERY, transport=Transport(fremd), warten=Uhr())

    assert TOKEN not in str(fehler.value)
    assert "OSError" in str(fehler.value)


@pytest.mark.parametrize("token, query, stichwort", [
    ("", QUERY, "Token"),
    ("   ", QUERY, "Token"),
    ("abc&q=1", QUERY, "Token"),
    (TOKEN, "", "Query"),
    (TOKEN, "12 34", "Query"),
    (TOKEN, "12&t=x", "Query"),
])
def test_ungueltige_zugangsdaten_werden_vor_dem_senden_abgelehnt(token, query, stichwort):
    transport = Transport()

    with pytest.raises(AbrufFehler, match=stichwort):
        abrufen(token, query, transport=transport, warten=Uhr())

    assert transport.urls == []


# ---------------------------------------------------------------- Speichern


def test_speichern_legt_ordner_und_datei_an(tmp_path):
    from datetime import datetime

    ziel = tmp_path / "flex"

    pfad = statement_speichern(STATEMENT, ziel, jetzt=datetime(2026, 10, 9, 20, 5))

    assert pfad.parent == ziel
    assert re.fullmatch(r"flex_20261009_[0-9a-f]{8}\.xml", pfad.name)
    assert pfad.read_bytes() == STATEMENT
    assert [p.name for p in ziel.iterdir()] == [pfad.name]  # keine Reste einer Zwischendatei


def test_gleicher_inhalt_ergibt_dieselbe_datei_auch_an_einem_anderen_tag(tmp_path):
    from datetime import datetime

    erste = statement_speichern(STATEMENT, tmp_path, jetzt=datetime(2026, 10, 9, 20, 5))
    zweite = statement_speichern(STATEMENT, tmp_path, jetzt=datetime(2026, 10, 10, 20, 5))

    assert zweite == erste
    assert len(list(tmp_path.iterdir())) == 1


def test_anderer_inhalt_ergibt_eine_neue_datei(tmp_path):
    from datetime import datetime

    erste = statement_speichern(STATEMENT, tmp_path, jetzt=datetime(2026, 10, 9, 20, 5))
    zweite = statement_speichern(STATEMENT + b"\n", tmp_path, jetzt=datetime(2026, 10, 9, 20, 6))

    assert zweite != erste
    assert erste.read_bytes() == STATEMENT  # nie überschrieben
    assert len(list(tmp_path.iterdir())) == 2


def test_speichern_im_projektverzeichnis_wird_abgelehnt():
    from datetime import datetime

    ziel = pathlib.Path(__file__).resolve().parents[1] / "flex_abruf_test_nicht_im_repo"

    with pytest.raises(ValueError, match="Projektverzeichnis"):
        statement_speichern(STATEMENT, ziel, jetzt=datetime(2026, 10, 9, 20, 5))

    assert not ziel.exists()


# ---------------------------------------------------------------- Befehl `journal abrufen`


@pytest.fixture
def umgebung(monkeypatch):
    monkeypatch.setenv("FLEX_TOKEN", TOKEN)
    monkeypatch.setenv("FLEX_QUERY_ID", QUERY)
    monkeypatch.delenv("FLEX_ZIEL", raising=False)
    return monkeypatch


def _transport_einsetzen(monkeypatch, *antworten) -> Transport:
    transport = Transport(*antworten)
    monkeypatch.setattr(flex_abruf, "standard_transport", transport)
    return transport


def _anzahl_ausfuehrungen(db) -> int:
    engine = create_db_engine(db)
    with engine.connect() as v:
        return v.execute(select(func.count()).select_from(executions)).scalar_one()


def test_befehl_ruft_ab_speichert_und_importiert(umgebung, migrated_db, tmp_path, capsys):
    _transport_einsetzen(umgebung, SEND_OK, STATEMENT)
    ziel = tmp_path / "flex"

    code = main(["abrufen", "--ziel", str(ziel), "--db", str(migrated_db)])

    ausgabe = capsys.readouterr()
    assert code == 0
    assert len(list(ziel.glob("flex_*.xml"))) == 1
    assert _anzahl_ausfuehrungen(migrated_db) == 10
    assert "10 neu" in ausgabe.out
    assert TOKEN not in ausgabe.out + ausgabe.err


def test_zweiter_abruf_mit_gleichem_inhalt_aendert_nichts(umgebung, migrated_db, tmp_path, capsys):
    _transport_einsetzen(umgebung, SEND_OK, STATEMENT, SEND_OK, STATEMENT)
    ziel = tmp_path / "flex"
    main(["abrufen", "--ziel", str(ziel), "--db", str(migrated_db)])
    capsys.readouterr()

    code = main(["abrufen", "--ziel", str(ziel), "--db", str(migrated_db)])

    assert code == 0
    assert "0 neu" in capsys.readouterr().out
    assert len(list(ziel.glob("flex_*.xml"))) == 1
    assert _anzahl_ausfuehrungen(migrated_db) == 10


def test_befehl_ohne_token_bricht_ab_ohne_anfrage(umgebung, migrated_db, tmp_path, capsys):
    umgebung.delenv("FLEX_TOKEN")
    transport = _transport_einsetzen(umgebung)

    code = main(["abrufen", "--ziel", str(tmp_path / "flex"), "--db", str(migrated_db)])

    assert code == 1
    assert "FLEX_TOKEN" in capsys.readouterr().err
    assert transport.urls == []


def test_befehl_ohne_query_id_bricht_ab(umgebung, migrated_db, tmp_path, capsys):
    umgebung.delenv("FLEX_QUERY_ID")
    transport = _transport_einsetzen(umgebung)

    code = main(["abrufen", "--ziel", str(tmp_path / "flex"), "--db", str(migrated_db)])

    assert code == 1
    assert "Query" in capsys.readouterr().err
    assert transport.urls == []


def test_query_id_als_option_hat_vorrang(umgebung, migrated_db, tmp_path):
    transport = _transport_einsetzen(umgebung, SEND_OK, STATEMENT)

    main(["abrufen", "--query-id", "999", "--ziel", str(tmp_path / "flex"),
          "--db", str(migrated_db)])

    assert "q=999" in transport.urls[0]


def test_ziel_aus_der_umgebung(umgebung, migrated_db, tmp_path):
    umgebung.setenv("FLEX_ZIEL", str(tmp_path / "aus_umgebung"))
    _transport_einsetzen(umgebung, SEND_OK, STATEMENT)

    assert main(["abrufen", "--db", str(migrated_db)]) == 0

    assert len(list((tmp_path / "aus_umgebung").glob("flex_*.xml"))) == 1


def test_befehl_ohne_ziel_bricht_ab(umgebung, migrated_db, capsys):
    transport = _transport_einsetzen(umgebung)

    code = main(["abrufen", "--db", str(migrated_db)])

    assert code == 1
    assert "Ziel" in capsys.readouterr().err
    assert transport.urls == []


def test_fehler_der_gegenstelle_schreibt_nichts_und_zeigt_keinen_token(
    umgebung, migrated_db, tmp_path, capsys
):
    _transport_einsetzen(umgebung, _fehler("1015", "Token is invalid."))
    ziel = tmp_path / "flex"

    code = main(["abrufen", "--ziel", str(ziel), "--db", str(migrated_db)])

    ausgabe = capsys.readouterr()
    assert code == 1
    assert "Abruf fehlgeschlagen" in ausgabe.err and "1015" in ausgabe.err
    assert TOKEN not in ausgabe.out + ausgabe.err
    assert not ziel.exists() or list(ziel.iterdir()) == []
    assert _anzahl_ausfuehrungen(migrated_db) == 0


def test_ziel_im_projektverzeichnis_wird_vor_dem_abruf_abgelehnt(
    umgebung, migrated_db, capsys
):
    transport = _transport_einsetzen(umgebung)
    ziel = pathlib.Path(__file__).resolve().parents[1] / "flex_abruf_test_nicht_im_repo"

    code = main(["abrufen", "--ziel", str(ziel), "--db", str(migrated_db)])

    assert code == 1
    assert "Projektverzeichnis" in capsys.readouterr().err
    assert transport.urls == []
    assert not ziel.exists()


def test_defektes_statement_bleibt_gespeichert_und_der_import_meldet(
    umgebung, migrated_db, tmp_path, capsys
):
    kaputt = STATEMENT.replace(b'assetCategory="OPT"', b'assetCategory="UNBEKANNT"', 1)
    assert kaputt != STATEMENT
    _transport_einsetzen(umgebung, SEND_OK, kaputt)
    ziel = tmp_path / "flex"

    code = main(["abrufen", "--ziel", str(ziel), "--db", str(migrated_db)])

    assert code == 1
    assert "Import fehlgeschlagen" in capsys.readouterr().err
    assert len(list(ziel.glob("flex_*.xml"))) == 1  # die Datei bleibt zur Prüfung
    assert _anzahl_ausfuehrungen(migrated_db) == 0


def _rebuild_ersetzen(monkeypatch) -> list[str]:
    """Der Fixture-Bestand ist für einen Rebuild zu klein (ihm fehlen
    Multiplikatoren); hier zählt, dass und wann der Befehl ihn aufruft."""
    from journal.rebuild import RebuildErgebnis

    aufrufe: list[str] = []

    def attrappe(db_pfad, **_):
        aufrufe.append(str(db_pfad))
        return RebuildErgebnis(0, 0, 0, 0, 0, 0, 0)

    monkeypatch.setattr("journal.cli.rebuild", attrappe)
    return aufrufe


def test_rebuild_option_baut_nach_dem_import_neu(umgebung, migrated_db, tmp_path, capsys):
    aufrufe = _rebuild_ersetzen(umgebung)
    _transport_einsetzen(umgebung, SEND_OK, STATEMENT)

    code = main(["abrufen", "--rebuild", "--ziel", str(tmp_path / "flex"),
                 "--db", str(migrated_db)])

    assert code == 0
    assert aufrufe == [str(migrated_db)]
    assert "Rebuild" in capsys.readouterr().out


def test_ohne_rebuild_option_wird_nicht_neu_gebaut(umgebung, migrated_db, tmp_path):
    aufrufe = _rebuild_ersetzen(umgebung)
    _transport_einsetzen(umgebung, SEND_OK, STATEMENT)

    assert main(["abrufen", "--ziel", str(tmp_path / "flex"), "--db", str(migrated_db)]) == 0

    assert aufrufe == []


def test_kein_rebuild_nach_fehlgeschlagenem_import(umgebung, migrated_db, tmp_path):
    aufrufe = _rebuild_ersetzen(umgebung)
    kaputt = STATEMENT.replace(b'assetCategory="OPT"', b'assetCategory="UNBEKANNT"', 1)
    _transport_einsetzen(umgebung, SEND_OK, kaputt)

    code = main(["abrufen", "--rebuild", "--ziel", str(tmp_path / "flex"),
                 "--db", str(migrated_db)])

    assert code == 1
    assert aufrufe == []
