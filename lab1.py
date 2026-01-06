import requests
import json
import time
import sys
from typing import Dict, Optional, Tuple

BASE_URL = "http://10.3.10.104:3000"
TIMEOUT = 3.0  # seconds för alla HTTP-anrop

class APIAutomation:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def get_token(self) -> Tuple[Optional[str], Optional[Dict]]:
        # Step 1: Hämta en ny token från API:et. Returnerar: (token, hela response_json)
        try:
            response = self.session.post(f"{self.base_url}/token", timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            token = data.get('token')

            if not token:
                print(f" Ingen token i svaret: {data}")
                return None, None

            print(f" Token erhållen: {token[:20]}..." if len(token) > 20 else f" Token erhållen: {token}")
            print(f" Måste verifieras inom: {data.get('verifyWithinMs', 'N/A')}ms")
            print(f" Måste claimas inom: {data.get('claimWithinMs', 'N/A')}ms")
            return token, data

        except requests.exceptions.RequestException as e:
            print(f" Fel vid hämtning av token: {e}")
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    print(" Response:", resp.text)
                except Exception:
                    pass
            return None, None
        except json.JSONDecodeError as e:
            print(f" JSON parse error: {e}")
            return None, None

    def verify_token(self, token: str) -> Optional[Dict]:
        # Step 2: Verifiera token inom tidsfönstret. Returnerar verifierings-svar (inkl. secret) eller None
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = self.session.post(f"{self.base_url}/verify", headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            secret = data.get('secret')

            if secret:
                print(f" Token verifierad! Secret: {secret[:20]}..." if len(secret) > 20 else " Token verifierad!")
                return data
            else:
                print(f" Ingen secret i verifieringssvaret: {data}")
                return None

        except requests.exceptions.RequestException as e:
            print(f" Verifieringsfel: {e}")
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    print(" Response:", resp.text)
                except Exception:
                    pass
            return None

    def claim_flag(self, token: str, secret: str) -> Optional[str]:
        # Step 3: Claima flaggan med token och secret. Returnerar: flaggan om lyckad, annars None
        try:
            headers = {'Authorization': f'Bearer {token}'}
            payload = {'secret': secret}
            response = self.session.post(
                f"{self.base_url}/claim",
                headers=headers,
                json=payload,
                timeout=TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            flag = data.get('flag')

            if flag:
                print(f" FLAGGA HITTAD: {flag}")
                return flag
            else:
                print(f" Ingen flagga i claim-svaret: {data}")
                return None

        except requests.exceptions.RequestException as e:
            print(f" Claim-fel: {e}")
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    print(" Response:", resp.text)
                except Exception:
                    pass
            return None

    def run_full_chain(self, max_attempts: int = 5) -> bool:
        # Kör hela API-kedjan automatiskt. Returnerar: True om flaggan hittades, annars False
        print(" Startar API-automation...")
        print("=" * 50)

        for attempt in range(1, max_attempts + 1):
            print(f"\n Försök {attempt}/{max_attempts}")
            print("-" * 30)

            # Steg 1: Hämta token
            token, token_data = self.get_token()
            if not token:
                print(" Misslyckades med token, försöker igen...")
                time.sleep(0.5)
                continue

            # Använd issuedAtMs om server skickar det, annars använd lokalt nu
            issued_ms = token_data.get('issuedAtMs', int(time.time() * 1000))
            verify_deadline = token_data.get('verifyWithinMs', 1000)
            claim_deadline = token_data.get('claimWithinMs', 2000)

            # Kontrollera att vi inte redan passerat verify-window
            now_ms = int(time.time() * 1000)
            if now_ms - issued_ms > verify_deadline:
                print(" Försent för verifiering enligt issuedAtMs, hämtar ny token...")
                continue

            # Steg 2: Verifiera token
            ver_data = self.verify_token(token)
            if not ver_data:
                print(" Misslyckades med verifiering, försöker igen...")
                continue

            # Server kan returnera updated claimWithinMs i verifieringssvaret
            claim_deadline = ver_data.get('claimWithinMs', claim_deadline)

            # Kontrollera claim-window innan claim
            now_ms = int(time.time() * 1000)
            if now_ms - issued_ms > claim_deadline:
                print(" Försent att claima flagga enligt issuedAtMs, försöker nytt token...")
                continue

            secret = ver_data.get('secret')
            if not secret:
                print(" Ingen secret efter verifiering, försöker igen...")
                continue

            # Steg 3: Claima flaggan
            flag = self.claim_flag(token, secret)
            if flag:
                return True

            # Om misslyckades med claim, vila kort innan nytt försök
            time.sleep(0.2)

        print(f"\n Misslyckades efter {max_attempts} försök")
        return False

    def test_connection(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/docs", timeout=TIMEOUT)
            if response.status_code == 200:
                print(" Ansluten till API")
                return True
            else:
                print(f" API svarar med status: {response.status_code}")
                return False
        except Exception as e:
            print(f" Kan inte ansluta till API: {e}")
            return False


def main():
    print(" API Automation Tool for Pentest Lab")
    print("=" * 50)

    automator = APIAutomation()

    if not automator.test_connection():
        print("Kontrollera att du är ansluten till Tailscale-nätet")
        print(f"och att {BASE_URL} är tillgänglig")
        return

    success = automator.run_full_chain(max_attempts=10)

    if success:
        print("\n Laboration slutförd!")
    else:
        print("\n Laboration misslyckades. Tips:")
        print("   1. Kontrollera Tailscale-anslutning")
        print("   2. Kolla Swagger-dokumentationen på /docs")
        print("   3. Anpassa tidsinställningar om nödvändigt")
        print("   4. Öka max_attempts i koden")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Avbruten av användare")
