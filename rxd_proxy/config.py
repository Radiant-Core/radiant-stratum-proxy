from dataclasses import dataclass
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


@dataclass
class Settings:
    # Initialize with None to force reading from environment in __post_init__
    ip: str = "0.0.0.0"
    port: int = 0
    rpcip: str = ""
    rpcport: int = 0
    rpcuser: str = ""
    rpcpass: str = ""
    proxy_signature: str = ""
    testnet: bool = False
    jobs: bool = False
    log_level: str = "INFO"
    verbose: bool = False  # Deprecated: use log_level instead
    enable_zmq: bool = False
    rxd_zmq_endpoint: str = ""
    static_share_difficulty: float = 1.0
    discord_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    enable_dashboard: bool = False
    dashboard_port: int = 8080
    enable_database: bool = False
    # Variable difficulty (per-miner) settings
    enable_vardiff: bool = False
    vardiff_target_interval: float = 15.0
    # Adjusted defaults for RXD GPU/ASIC mining (SHA512/256d)
    vardiff_min_difficulty: float = 100.0       # Prevents share spam
    vardiff_max_difficulty: float = 10000000.0  # 10M for large ASIC farms
    vardiff_start_difficulty: float = 10000.0   # Good starting point for GPUs
    vardiff_retarget_shares: int = 20
    vardiff_retarget_time: float = 300.0
    vardiff_up_step: float = 2.0
    vardiff_down_step: float = 0.5
    vardiff_ema_alpha: float = 0.3
    vardiff_inactivity_lower: float = 90.0
    vardiff_inactivity_multiples: float = 6.0
    vardiff_inactivity_drop_factor: float = 0.5
    vardiff_state_path: str = "data/vardiff_state.json"
    vardiff_warm_start_minutes: int = 60
    vardiff_chain_headroom: float = (
        0.9  # fraction of chain difficulty used as upper cap
    )

    def __post_init__(self):
        """Load settings from environment variables at instance creation time"""
        self.port = int(os.getenv("STRATUM_PORT", "54321"))
        self.rpcip = os.getenv("RXD_RPC_HOST", os.getenv("RXD_RPC_IP", "radiant"))
        self.rpcport = int(os.getenv("RXD_RPC_PORT", "7332"))
        self.rpcuser = os.getenv("RXD_RPC_USER", "")
        self.rpcpass = os.getenv("RXD_RPC_PASS", "")
        self.proxy_signature = os.getenv("PROXY_SIGNATURE", "/radiant-stratum-proxy/")
        self.testnet = os.getenv("TESTNET", "false").lower() == "true"
        self.jobs = os.getenv("SHOW_JOBS", "false").lower() == "true"

        # Log level configuration (LOG_LEVEL takes precedence over VERBOSE)
        log_level_env = os.getenv("LOG_LEVEL", "").upper()
        if log_level_env:
            self.log_level = log_level_env
        else:
            # Fallback: check VERBOSE for backwards compatibility
            self.verbose = os.getenv("VERBOSE", "false").lower() == "true"
            self.log_level = "DEBUG" if self.verbose else "INFO"

        # ZMQ Configuration - read at instance creation time
        self.enable_zmq = os.getenv("ENABLE_ZMQ", "true").lower() == "true"
        # Auto-select ZMQ port based on network if not explicitly set
        zmq_endpoint_env = os.getenv("RXD_ZMQ_ENDPOINT", "")
        if zmq_endpoint_env:
            self.rxd_zmq_endpoint = zmq_endpoint_env
        else:
            # Use testnet port (39332) or mainnet port (29332) based on TESTNET setting
            default_zmq_port = "39332" if self.testnet else "29332"
            self.rxd_zmq_endpoint = f"tcp://radiant:{default_zmq_port}"
        # Static share difficulty (used when VarDiff is disabled)
        # This is the exact difficulty value miners will use
        # GPU default: 1.0, ASIC default: 512.0
        self.static_share_difficulty = float(
            os.getenv("STATIC_SHARE_DIFFICULTY", "1.0")
        )
        # Notification settings
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        # Dashboard settings
        self.enable_dashboard = os.getenv("ENABLE_DASHBOARD", "false").lower() == "true"
        self.dashboard_port = int(os.getenv("DASHBOARD_PORT", "8080"))
        self.enable_database = os.getenv("ENABLE_DATABASE", "false").lower() == "true"
        # VarDiff settings
        self.enable_vardiff = os.getenv("ENABLE_VARDIFF", "false").lower() == "true"
        try:
            self.vardiff_target_interval = float(
                os.getenv("VARDIFF_TARGET_SHARE_TIME", "15.0")
            )
        except ValueError:
            self.vardiff_target_interval = 15.0
        # Extended vardiff tunables - defaults tuned for GPU/ASIC mining
        self.vardiff_min_difficulty = float(
            os.getenv("VARDIFF_MIN_DIFFICULTY", "100.0")
        )
        self.vardiff_max_difficulty = float(os.getenv("VARDIFF_MAX_DIFFICULTY", "10000000.0"))
        self.vardiff_start_difficulty = float(
            os.getenv("VARDIFF_START_DIFFICULTY", "10000.0")
        )
        self.vardiff_retarget_shares = int(os.getenv("VARDIFF_RETARGET_SHARES", "20"))
        self.vardiff_retarget_time = float(os.getenv("VARDIFF_RETARGET_TIME", "300.0"))
        self.vardiff_up_step = float(os.getenv("VARDIFF_UP_STEP", "2.0"))
        self.vardiff_down_step = float(os.getenv("VARDIFF_DOWN_STEP", "0.5"))
        self.vardiff_ema_alpha = float(os.getenv("VARDIFF_EMA_ALPHA", "0.3"))
        self.vardiff_inactivity_lower = float(
            os.getenv("VARDIFF_INACTIVITY_LOWER", "90.0")
        )
        self.vardiff_inactivity_multiples = float(
            os.getenv("VARDIFF_INACTIVITY_MULTIPLES", "6.0")
        )
        self.vardiff_inactivity_drop_factor = float(
            os.getenv("VARDIFF_INACTIVITY_DROP_FACTOR", "0.5")
        )
        # Starting difficulty for new miners (defaults to 1000 for faster convergence)
        self.vardiff_start_difficulty = float(
            os.getenv("VARDIFF_START_DIFFICULTY", "1000.0")
        )
        self.vardiff_state_path = os.getenv(
            "VARDIFF_STATE_PATH", "data/vardiff_state.json"
        )
        self.vardiff_warm_start_minutes = int(
            os.getenv("VARDIFF_WARM_START_MINUTES", "60")
        )
        try:
            self.vardiff_chain_headroom = float(
                os.getenv("VARDIFF_CHAIN_HEADROOM", "0.9")
            )
            if self.vardiff_chain_headroom <= 0 or self.vardiff_chain_headroom > 1:
                self.vardiff_chain_headroom = 0.9
        except ValueError:
            self.vardiff_chain_headroom = 0.9

    @property
    def node_url(self) -> str:
        return f"http://{self.rpcuser}:{self.rpcpass}@{self.rpcip}:{self.rpcport}"
