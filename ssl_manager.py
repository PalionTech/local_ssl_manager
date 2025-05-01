#!/usr/bin/env python3
import argparse
import os
import subprocess
from pathlib import Path
import sys
import logging
from typing import Tuple, List, Dict
from datetime import datetime
import json
import curses


class LocalSSLManager:
    def __init__(self):
        self.base_dir = Path.home() / ".local-ssl-manager"
        self.certs_dir = self.base_dir / "certs"
        self.logs_dir = self.base_dir / "logs"
        self.config_dir = self.base_dir / "config"
        self.hosts_backup = self.base_dir / "hosts.backup"
        self.metadata_file = self.config_dir / "certificates.json"
        self.setup_directories()
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.logs_dir / "ssl-manager.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def setup_directories(self):
        """Erstellt die notwendigen Verzeichnisse für Zertifikate und Konfigurationen"""
        for directory in [self.base_dir, self.certs_dir, self.config_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        if not self.metadata_file.exists():
            self.save_metadata({})

    def save_metadata(self, metadata: Dict):
        """Speichert Metadaten der Zertifikate"""
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    def load_metadata(self) -> Dict:
        """Lädt Metadaten der Zertifikate"""
        if not self.metadata_file.exists():
            return {}
        with open(self.metadata_file, "r") as f:
            return json.load(f)

    def validate_domain(self, domain: str) -> bool:
        """Überprüft, ob der Domain-Name gültig ist"""
        if not domain or len(domain) > 255:
            return False

        parts = domain.split(".")
        for part in parts:
            if not part:  # Leere Teile sind nicht erlaubt
                return False
            if part.startswith("-") or part.endswith(
                "-"
            ):  # Bindestrich am Anfang oder Ende ist nicht erlaubt
                return False
            if not all(
                c.isalnum() or c == "-" for c in part
            ):  # Nur alphanumerische Zeichen und Bindestriche
                return False

        return True

    def check_domain_exists(self, domain: str) -> bool:
        """Überprüft, ob die Domain bereits konfiguriert ist"""
        metadata = self.load_metadata()
        if domain in metadata:
            return True

        with open("/etc/hosts", "r") as f:
            return domain in f.read()

    def setup_browser_trust(self):
        """Richtet Vertrauensstellung für Browser ein"""
        try:
            # Stelle sicher, dass mkcert installiert ist
            try:
                subprocess.run(["which", "mkcert"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self.logger.info("Installing mkcert...")
                subprocess.run(["brew", "install", "mkcert"], check=True)

            # Initialisiere mkcert und installiere Root-Zertifikat
            self.logger.info("Setting up root certificate...")
            subprocess.run(["mkcert", "-install"], check=True)

            # Finde den Pfad zum Root-Zertifikat
            root_ca_path = Path.home() / "Library/Application Support/mkcert/rootCA.pem"
            if not root_ca_path.exists():
                # Alternative Pfade prüfen
                alt_paths = [
                    Path.home() / ".local/share/mkcert/rootCA.pem",
                    Path("/usr/local/share/mkcert/rootCA.pem"),
                ]
                for path in alt_paths:
                    if path.exists():
                        root_ca_path = path
                        break
                else:
                    # Finde den Pfad durch Ausführen von mkcert -CAROOT
                    try:
                        ca_root = subprocess.run(
                            ["mkcert", "-CAROOT"],
                            capture_output=True,
                            text=True,
                            check=True,
                        ).stdout.strip()
                        root_ca_path = Path(ca_root) / "rootCA.pem"
                    except subprocess.CalledProcessError as e:
                        raise RuntimeError(f"Konnte Root-Zertifikat nicht finden: {e}")

            if not root_ca_path.exists():
                raise FileNotFoundError(
                    f"Root-Zertifikat nicht gefunden unter: {root_ca_path}"
                )

            self.logger.info(f"Found root certificate at: {root_ca_path}")

            # Füge Zertifikat zum System-Keychain hinzu
            subprocess.run(
                [
                    "sudo",
                    "security",
                    "add-trusted-cert",
                    "-d",
                    "-r",
                    "trustRoot",
                    "-k",
                    "/Library/Keychains/System.keychain",
                    str(root_ca_path),
                ],
                check=True,
            )

            self.logger.info("Root certificate successfully installed")

        except Exception as e:
            self.logger.error(
                f"Fehler beim Einrichten der Browser-Vertrauensstellung: {e}"
            )
            self.logger.info("Fahre fort ohne erweiterte Browser-Vertrauensstellung...")
            # Wir lassen das Skript weiterlaufen, auch wenn die Vertrauensstellung fehlschlägt

    def backup_hosts_file(self):
        """Erstellt ein Backup der hosts-Datei"""
        hosts_path = "/etc/hosts"
        if not os.path.exists(self.hosts_backup):
            subprocess.run(["sudo", "cp", hosts_path, self.hosts_backup], check=True)

    def update_hosts_file(self, domain: str, remove: bool = False):
        """Aktualisiert die /etc/hosts Datei"""
        self.backup_hosts_file()
        temp_hosts = self.base_dir / "hosts.temp"

        with open("/etc/hosts", "r") as f:
            hosts_content = f.read().splitlines()

        if remove:
            # Entferne die Domain-Zeile
            hosts_content = [
                line
                for line in hosts_content
                if not (domain in line and "127.0.0.1" in line)
            ]
        else:
            # Füge Domain hinzu wenn sie noch nicht existiert
            domain_line = f"127.0.0.1 {domain}"
            if not any(domain in line for line in hosts_content):
                hosts_content.append(domain_line)

        with temp_hosts.open("w") as f:
            f.write("\n".join(hosts_content) + "\n")

        subprocess.run(["sudo", "cp", str(temp_hosts), "/etc/hosts"], check=True)
        temp_hosts.unlink()

    def create_ssl_certificate(self, domain: str) -> Tuple[Path, Path]:
        """Erstellt ein selbstsigniertes SSL-Zertifikat"""
        cert_path = self.certs_dir / f"{domain}.crt"
        key_path = self.certs_dir / f"{domain}.key"

        # Erstelle SSL-Zertifikat mit mkcert
        subprocess.run(
            [
                "mkcert",
                "-cert-file",
                str(cert_path),
                "-key-file",
                str(key_path),
                domain,
            ],
            check=True,
        )

        return cert_path, key_path

    def setup_local_domain(self, domain: str):
        """Hauptfunktion zum Einrichten einer lokalen Domain mit SSL"""
        if not self.validate_domain(domain):
            raise ValueError(f"Ungültiger Domain-Name: {domain}")

        if self.check_domain_exists(domain):
            raise ValueError(f"Die Domain {domain} ist bereits konfiguriert!")

        self.logger.info(f"Richte Domain {domain} ein...")

        # Stelle Browser-Vertrauensstellung ein
        self.setup_browser_trust()

        # Aktualisiere hosts-Datei
        self.update_hosts_file(domain)
        self.logger.info("Hosts-Datei aktualisiert")

        # Erstelle SSL-Zertifikat
        cert_path, key_path = self.create_ssl_certificate(domain)
        self.logger.info(f"SSL-Zertifikat erstellt: {cert_path}")

        # Aktualisiere Metadaten
        metadata = self.load_metadata()
        metadata[domain] = {
            "created_at": datetime.now().isoformat(),
            "cert_path": str(cert_path),
            "key_path": str(key_path),
        }
        self.save_metadata(metadata)

        return {
            "domain": domain,
            "cert_path": str(cert_path),
            "key_path": str(key_path),
        }

    def get_domain_hierarchy(self) -> List[Tuple[str, datetime]]:
        """Erstellt eine hierarchische Liste der Domains mit Erstellungsdatum"""
        metadata = self.load_metadata()
        domains = []

        for domain, data in metadata.items():
            created_at = datetime.fromisoformat(data["created_at"])
            domains.append((domain, created_at))

        # Sortiere nach Domain-Hierarchie und Datum
        return sorted(domains, key=lambda x: (x[0].count("."), x[0]))

    def delete_certificate(self, domain: str):
        """Löscht ein Zertifikat und alle zugehörigen Dateien"""
        metadata = self.load_metadata()

        if domain not in metadata:
            raise ValueError(f"Zertifikat für {domain} nicht gefunden!")

        cert_data = metadata[domain]

        # Lösche Zertifikatsdateien
        cert_path = Path(cert_data["cert_path"])
        key_path = Path(cert_data["key_path"])

        if cert_path.exists():
            cert_path.unlink()
        if key_path.exists():
            key_path.unlink()

        # Entferne Domain aus hosts-Datei
        self.update_hosts_file(domain, remove=True)

        # Aktualisiere Metadaten
        del metadata[domain]
        self.save_metadata(metadata)

        self.logger.info(f"Zertifikat für {domain} wurde gelöscht")


def show_domain_selector(domains: List[Tuple[str, datetime]]) -> str:
    """Zeigt einen interaktiven Domain-Selector"""

    def main(stdscr):
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)

        current_row = 0

        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()

            # Header
            header = "Wähle eine Domain zum Löschen (Pfeiltasten zum Navigieren, Enter zum Auswählen)"
            stdscr.addstr(0, 0, header, curses.A_BOLD)

            # Domains anzeigen
            for idx, (domain, created_at) in enumerate(domains):
                # Bestimme Einrückung basierend auf Domain-Hierarchie
                indent = domain.count(".") * 2
                display_str = f"{' ' * indent}{domain} (erstellt: {created_at.strftime('%Y-%m-%d %H:%M')})"

                # Markiere ausgewählte Zeile
                if idx == current_row:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(idx + 2, 0, display_str.ljust(width - 1))
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(idx + 2, 0, display_str)

            # Tasteneingabe verarbeiten
            key = stdscr.getch()
            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(domains) - 1:
                current_row += 1
            elif key == ord("\n"):  # Enter-Taste
                return domains[current_row][0]

            stdscr.refresh()

    return curses.wrapper(main)


def main():
    parser = argparse.ArgumentParser(description="Lokaler SSL-Zertifikat-Manager")
    parser.add_argument(
        "command", choices=["create", "delete"], help="Befehl: create oder delete"
    )
    parser.add_argument("--domain", help="Domain-Name (z.B. projekt.local)")

    args = parser.parse_args()

    manager = LocalSSLManager()

    try:
        if args.command == "create":
            if not args.domain:
                parser.error("Für 'create' wird --domain benötigt")

            config = manager.setup_local_domain(args.domain)
            print(f"\nErfolgreich eingerichtet!")
            print(f"Domain: {config['domain']}")
            print(f"Die Domain wurde zu 127.0.0.1 hinzugefügt")
            print(f"Zertifikat: {config['cert_path']}")
            print(f"Privater Schlüssel: {config['key_path']}")

        elif args.command == "delete":
            domains = manager.get_domain_hierarchy()
            if not domains:
                print("Keine Zertifikate vorhanden!")
                return

            selected_domain = show_domain_selector(domains)
            if selected_domain:
                manager.delete_certificate(selected_domain)
                print(f"\nZertifikat für {selected_domain} wurde erfolgreich gelöscht!")

    except ValueError as e:
        print(f"Fehler: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unerwarteter Fehler: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
