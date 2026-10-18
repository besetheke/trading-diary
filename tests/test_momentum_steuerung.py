# ruff: noqa: E501
"""Schalter für Momentum Lab: Port-Erkennung, Schutz vor fremden Prozessen, Endpunkt."""
from api import momentum_steuerung as ms

NETSTAT = """
  Proto  Lokale Adresse         Remoteadresse          Status           PID
  TCP    0.0.0.0:135            0.0.0.0:0              ABHÖREN          1000
  TCP    127.0.0.1:8501         0.0.0.0:0              ABHÖREN          4242
  TCP    127.0.0.1:18501        0.0.0.0:0              ABHÖREN          7777
  TCP    127.0.0.1:8501         127.0.0.1:50000        HERGESTELLT      4242
"""


def test_pid_am_port_nur_exakter_port_und_nur_abhoerend():
    assert ms.pid_am_port(NETSTAT, 8501) == 4242
    assert ms.pid_am_port(NETSTAT, 18501) == 7777
    assert ms.pid_am_port(NETSTAT, 8502) is None
    assert ms.pid_am_port("  TCP    0.0.0.0:8501   0.0.0.0:0   LISTENING   55", 8501) == 55


def test_nur_momentum_lab_wird_erkannt():
    ok = r'C:\10_Coding\momentum-lab\.venv\Scripts\python.exe -m streamlit run C:\10_Coding\momentum-lab\src\momentum_lab\app.py'
    assert ms.ist_momentum_lab(ok)
    assert not ms.ist_momentum_lab(r"C:\Python\python.exe -m http.server 8501")
    assert not ms.ist_momentum_lab("")


def test_beenden_verweigert_fremden_prozess(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(ms, "_ausgabe", lambda befehl: aufrufe.append(befehl) or NETSTAT)
    monkeypatch.setattr(ms, "_kommandozeile", lambda pid: "python fremd.py")
    ok, text = ms.beenden()
    assert not ok and "anderen Programm" in text
    assert all(b[0] != "taskkill" for b in aufrufe)


def test_beenden_stoppt_momentum_lab_samt_unterprozessen(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(ms, "_ausgabe", lambda befehl: aufrufe.append(befehl) or NETSTAT)
    monkeypatch.setattr(ms, "_kommandozeile", lambda pid: r"python -m streamlit run x\momentum_lab\app.py")
    ok, _ = ms.beenden()
    assert ok
    assert ["taskkill", "/PID", "4242", "/T", "/F"] in aufrufe


def test_starten_ohne_laufende_instanz_ruft_den_starter_ohne_browser(monkeypatch, tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "start_momentum_lab_hidden.ps1").write_text("", encoding="utf-8")
    monkeypatch.setenv("MOMENTUM_LAB_ORDNER", str(tmp_path))
    monkeypatch.setattr(ms, "laeuft", lambda: False)
    gestartet = []
    monkeypatch.setattr(ms.subprocess, "Popen", lambda befehl, **kw: gestartet.append(befehl))
    ok, _ = ms.starten()
    assert ok and "-NoBrowser" in gestartet[0] and gestartet[0][-2].endswith("start_momentum_lab_hidden.ps1")


def test_starten_wenn_es_schon_laeuft_startet_nichts(monkeypatch):
    monkeypatch.setattr(ms, "laeuft", lambda: True)
    monkeypatch.setattr(ms.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Start")))
    assert ms.starten()[0]


def test_beenden_beendet_auch_den_hängenden_starter_zuerst(monkeypatch):
    """Ursache „Momentum Lab lässt sich nicht einschalten“: der Starter blieb nach dem Stopp stehen."""
    aufrufe = []

    def ausgabe(befehl):
        aufrufe.append(befehl)
        return "777\n" if befehl[0] == "powershell" and "start_momentum_lab_hidden" in befehl[-1] else NETSTAT

    monkeypatch.setattr(ms, "_ausgabe", ausgabe)
    monkeypatch.setattr(ms, "_kommandozeile", lambda pid: r"python -m streamlit run x\momentum_lab\app.py")
    assert ms.beenden()[0]
    starter = ["taskkill", "/PID", "777", "/T", "/F"]
    server = ["taskkill", "/PID", "4242", "/T", "/F"]
    assert starter in aufrufe and server in aufrufe and aufrufe.index(starter) < aufrufe.index(server)


def test_starten_raeumt_alte_starter_vor_dem_start_ab(monkeypatch, tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "start_momentum_lab_hidden.ps1").write_text("", encoding="utf-8")
    monkeypatch.setenv("MOMENTUM_LAB_ORDNER", str(tmp_path))
    monkeypatch.setattr(ms, "laeuft", lambda: False)
    aufrufe = []
    monkeypatch.setattr(ms, "_ausgabe", lambda b: aufrufe.append(b) or ("888\n" if b[0] == "powershell" else ""))
    monkeypatch.setattr(ms.subprocess, "Popen", lambda befehl, **kw: None)
    assert ms.starten_mit_aufraeumen()[0]
    assert ["taskkill", "/PID", "888", "/T", "/F"] in aufrufe
