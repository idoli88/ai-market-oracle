import openai
from oracle.config import settings
from oracle.logger import setup_logger
from oracle.prompts import SYSTEM_PROMPT
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = setup_logger(__name__)

class OracleBrain:
    def __init__(self):
        """
        Initialize the OracleBrain with OpenAI client.
        """
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not found in settings.")
        
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.debug("OracleBrain initialized")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def analyze(self, market_summary: str) -> str:
        """
        Send the market summary to the LLM and get a trade recommendation.
        
        Args:
            market_summary (str): Text summary of technical indicators.
            
        Returns:
            str: The LLM's analysis and recommendation in Hebrew.
        """
        logger.info("Sending market summary to OpenAI for analysis")
        
        # System prompt is imported from oracle.prompts

        response = self.client.chat.completions.create(
            model="gpt-4o",  # Or gpt-4-turbo / gpt-3.5-turbo depending on budget
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Here is today's market summary:\n\n{market_summary}"}
            ],
            temperature=0.7,
        )
        content = response.choices[0].message.content.strip()
        logger.info("Received analysis from OpenAI")
        return content
