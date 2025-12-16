import requests
import logging
from typing import Dict, Optional, List
from datetime import datetime
from oracle.config import settings

logger = logging.getLogger(__name__)

class SecEdgarProvider:
    """Provider for SEC EDGAR fundamentals data."""

    BASE_URL = "https://data.sec.gov"
    HEADERS = {"User-Agent": settings.SEC_USER_AGENT}

    def __init__(self):
        self._cik_cache = {}  # ticker -> CIK mapping

    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Get CIK for ticker. Uses cache to minimize API calls.
        """
        ticker = ticker.upper()

        if ticker in self._cik_cache:
            return self._cik_cache[ticker]

        try:
            # Use SEC's company tickers JSON
            url = f"{self.BASE_URL}/files/company_tickers.json"
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()

            data = response.json()
            # data is a dict with numeric keys, each containing ticker/cik_str
            for item in data.values():
                if item.get('ticker', '').upper() == ticker:
                    cik = str(item['cik_str']).zfill(10)  # Pad to 10 digits
                    self._cik_cache[ticker] = cik
                    logger.info(f"Found CIK for {ticker}: {cik}")
                    return cik

            logger.warning(f"No CIK found for {ticker}")
            return None

        except Exception as e:
            logger.error(f"Error getting CIK for {ticker}: {e}")
            return None

    def get_latest_filing(self, cik: str) -> Optional[Dict]:
        """
        Get the latest 10-Q or 10-K filing for a CIK.
        Returns dict with accession_number, filing_date, form.
        """
        try:
            url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()

            data = response.json()
            filings = data.get('filings', {}).get('recent', {})

            # Iterate through recent filings
            forms = filings.get('form', [])
            accessions = filings.get('accessionNumber', [])
            dates = filings.get('filingDate', [])

            for i, form in enumerate(forms):
                if form in ['10-Q', '10-K']:
                    return {
                        'form': form,
                        'accession_number': accessions[i],
                        'filing_date': dates[i]
                    }

            logger.warning(f"No 10-Q/10-K filings found for CIK {cik}")
            return None

        except Exception as e:
            logger.error(f"Error getting filings for CIK {cik}: {e}")
            return None

    def extract_kpis(self, cik: str) -> Dict:
        """
        Extract key financial metrics from SEC companyfacts API.
        Returns dict with available KPIs or N/A.
        """
        try:
            url = f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()

            data = response.json()
            facts = data.get('facts', {}).get('us-gaap', {})

            kpis = {}

            # Helper to get latest value for a concept
            def get_latest_value(concept_name: str) -> Optional[float]:
                concept = facts.get(concept_name, {})
                units = concept.get('units', {})

                # Try USD first, then shares
                for unit_type in ['USD', 'shares']:
                    if unit_type in units:
                        values = units[unit_type]
                        # Get most recent value (sorted by end date)
                        if values:
                            latest = sorted(values, key=lambda x: x.get('end', ''), reverse=True)[0]
                            return latest.get('val')
                return None

            # Extract KPIs with fallback names
            revenue = get_latest_value('Revenues') or get_latest_value('RevenueFromContractWithCustomerExcludingAssessedTax')
            if revenue:
                kpis['revenue'] = revenue / 1_000_000_000  # Convert to billions

            net_income = get_latest_value('NetIncomeLoss')
            if net_income:
                kpis['net_income'] = net_income / 1_000_000  # Convert to millions

            eps = get_latest_value('EarningsPerShareBasic')
            if eps:
                kpis['eps'] = eps

            cash = get_latest_value('CashAndCashEquivalentsAtCarryingValue')
            if cash:
                kpis['cash'] = cash / 1_000_000_000  # Convert to billions

            # Debt - try to combine long-term and current
            long_term_debt = get_latest_value('LongTermDebt') or 0
            current_debt = get_latest_value('DebtCurrent') or 0
            total_debt = long_term_debt + current_debt
            if total_debt > 0:
                kpis['debt'] = total_debt / 1_000_000_000  # Convert to billions

            logger.info(f"Extracted KPIs for CIK {cik}: {kpis}")
            return kpis

        except Exception as e:
            logger.error(f"Error extracting KPIs for CIK {cik}: {e}")
            return {}

    def get_fundamentals(self, ticker: str) -> Optional[Dict]:
        """
        Main entry point: Get fundamentals for a ticker.
        Returns dict with KPIs and latest filing info.
        """
        cik = self.get_cik(ticker)
        if not cik:
            return None

        latest_filing = self.get_latest_filing(cik)
        kpis = self.extract_kpis(cik)

        return {
            'ticker': ticker,
            'cik': cik,
            'kpis': kpis,
            'latest_filing': latest_filing,
            'fetched_at': datetime.now().isoformat()
        }
