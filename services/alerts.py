"""
Real-time alert service for trading signals.
Monitors signals and dispatches email notifications.
"""

import smtplib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from string import Template
from typing import Callable

from domain.algorithm_signals import AlgorithmSignal, AlgorithmSignalType
from domain.strategies.signal_generator import generate_signals_for_ticker


logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    """Configuration for alert service."""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = ""
    to_emails: list[str] = field(default_factory=list)

    poll_interval_seconds: int = 300
    min_confidence: float = 0.5
    signal_types: list[AlgorithmSignalType] = field(default_factory=lambda: [
        AlgorithmSignalType.LONG_ENTRY,
        AlgorithmSignalType.SHORT_ENTRY,
    ])

    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0


@dataclass
class AlertState:
    """Tracks last known signals to avoid duplicate alerts."""
    last_signals: dict[str, dict[str, AlgorithmSignal]] = field(default_factory=dict)
    last_check: datetime | None = None
    alerts_sent_today: int = 0


class AlertEngine:
    """
    Engine for monitoring trading signals and dispatching alerts.

    Usage:
        config = AlertConfig(
            smtp_user="user@gmail.com",
            smtp_password="app-password",
            from_email="user@gmail.com",
            to_emails=["recipient@example.com"],
        )
        engine = AlertEngine(config)

        new_signals = engine.check_signals(tickers, price_data_map)
        engine.send_alerts(new_signals)
    """

    def __init__(self, config: AlertConfig):
        self.config = config
        self.state = AlertState()
        self._price_fetcher: Callable | None = None

    def set_price_fetcher(self, fetcher: Callable[[list[str]], dict[str, list[dict]]]):
        """Set function to fetch price data for tickers."""
        self._price_fetcher = fetcher

    def is_market_hours(self) -> bool:
        """Check if current time is within market hours (EST)."""
        now = datetime.now()
        market_open = now.replace(hour=self.config.market_open_hour, minute=self.config.market_open_minute)
        market_close = now.replace(hour=self.config.market_close_hour, minute=self.config.market_close_minute)

        if now.weekday() >= 5:
            return False

        return market_open <= now <= market_close

    def check_signals(
        self,
        tickers: list[str],
        price_data_map: dict[str, list[dict]],
        spy_data: list[dict] | None = None,
    ) -> list[AlgorithmSignal]:
        """
        Check for new signals across all tickers and strategies.

        Args:
            tickers: List of tickers to check
            price_data_map: Price data for each ticker
            spy_data: Optional SPY data for market context

        Returns:
            List of new signals that haven't been alerted yet
        """
        new_signals = []

        for ticker in tickers:
            if ticker not in price_data_map:
                continue

            signals = generate_signals_for_ticker(
                ticker=ticker,
                price_data=price_data_map[ticker],
                spy_data=spy_data,
            )

            for signal in signals:
                if signal.confidence < self.config.min_confidence:
                    continue
                if signal.signal_type not in self.config.signal_types:
                    continue

                if self._is_new_signal(signal):
                    new_signals.append(signal)
                    self._update_state(signal)

        self.state.last_check = datetime.now()
        return new_signals

    def _is_new_signal(self, signal: AlgorithmSignal) -> bool:
        """Check if signal is new (not already alerted)."""
        ticker_signals = self.state.last_signals.get(signal.ticker, {})
        last_signal = ticker_signals.get(signal.algorithm_id)

        if last_signal is None:
            return True

        time_diff = signal.timestamp - last_signal.timestamp
        if (signal.signal_type == last_signal.signal_type and
            time_diff < timedelta(hours=1)):
            return False

        return True

    def _update_state(self, signal: AlgorithmSignal):
        """Update state with new signal."""
        if signal.ticker not in self.state.last_signals:
            self.state.last_signals[signal.ticker] = {}
        self.state.last_signals[signal.ticker][signal.algorithm_id] = signal

    def send_alerts(self, signals: list[AlgorithmSignal]) -> int:
        """
        Send email alerts for signals.

        Args:
            signals: Signals to alert on

        Returns:
            Number of alerts sent
        """
        if not signals:
            return 0

        if not self.config.to_emails:
            logger.warning("No recipients configured for alerts")
            return 0

        alerts_sent = 0

        for signal in signals:
            try:
                self._send_email(signal)
                alerts_sent += 1
                self.state.alerts_sent_today += 1
                logger.info(f"Alert sent for {signal.ticker} {signal.signal_type.name}")
            except Exception as e:
                logger.error(f"Failed to send alert for {signal.ticker}: {e}")

        return alerts_sent

    def _send_email(self, signal: AlgorithmSignal):
        """Send email alert for a single signal."""
        subject = f"[FINTEL] {signal.signal_type.name} Signal: {signal.ticker}"

        body = self._format_signal_email(signal)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.from_email
        msg["To"] = ", ".join(self.config.to_emails)

        text_part = MIMEText(body, "plain")
        msg.attach(text_part)

        html_body = self._format_signal_html(signal)
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            server.starttls()
            server.login(self.config.smtp_user, self.config.smtp_password)
            server.sendmail(
                self.config.from_email,
                self.config.to_emails,
                msg.as_string(),
            )

    def _extract_signal_data(self, signal: AlgorithmSignal) -> dict:
        """Extract and format signal data for templating. Single source of truth."""
        data = {
            "ticker": signal.ticker,
            "signal_type": signal.signal_type.name,
            "algorithm_name": signal.algorithm_name,
            "confidence": f"{signal.confidence:.1%}",
            "price": f"${signal.price_at_signal:.2f}",
            "timestamp": signal.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "rationale": signal.rationale,
            "is_long": "LONG" in signal.signal_type.name,
            "signal_color": "#22c55e" if "LONG" in signal.signal_type.name else "#ef4444",
        }

        # Optional levels (entry/stop/target)
        if signal.suggested_entry:
            data["entry"] = f"${signal.suggested_entry:.2f}"
            data["has_entry"] = True
        else:
            data["entry"] = ""
            data["has_entry"] = False

        if signal.suggested_stop:
            data["stop"] = f"${signal.suggested_stop:.2f}"
            data["has_stop"] = True
        else:
            data["stop"] = ""
            data["has_stop"] = False

        if signal.suggested_target:
            data["target"] = f"${signal.suggested_target:.2f}"
            data["has_target"] = True
        else:
            data["target"] = ""
            data["has_target"] = False

        data["has_levels"] = data["has_entry"] or data["has_stop"] or data["has_target"]

        # Indicators
        data["rsi"] = f"{signal.indicators.rsi:.1f}" if signal.indicators.rsi else ""
        data["macd"] = f"{signal.indicators.macd_histogram:.3f}" if signal.indicators.macd_histogram else ""
        data["sma_50"] = f"${signal.indicators.sma_50:.2f}" if signal.indicators.sma_50 else ""
        data["has_rsi"] = bool(signal.indicators.rsi)
        data["has_macd"] = bool(signal.indicators.macd_histogram)
        data["has_sma_50"] = bool(signal.indicators.sma_50)

        return data

    def _format_signal_email(self, signal: AlgorithmSignal) -> str:
        """Format signal as plain text email using template."""
        data = self._extract_signal_data(signal)

        lines = [
            "Trading Signal Alert",
            "=" * 40,
            "",
            f"Ticker: {data['ticker']}",
            f"Signal: {data['signal_type']}",
            f"Algorithm: {data['algorithm_name']}",
            f"Confidence: {data['confidence']}",
            f"Price: {data['price']}",
            f"Time: {data['timestamp']}",
            "",
            "Rationale:",
            data['rationale'],
            "",
        ]

        if data['has_entry']:
            lines.append(f"Entry: {data['entry']}")
        if data['has_stop']:
            lines.append(f"Stop Loss: {data['stop']}")
        if data['has_target']:
            lines.append(f"Target: {data['target']}")

        if data['has_entry'] or data['has_stop'] or data['has_target']:
            lines.append("")

        lines.append("Indicators:")
        if data['has_rsi']:
            lines.append(f"  RSI: {data['rsi']}")
        if data['has_macd']:
            lines.append(f"  MACD: {data['macd']}")
        if data['has_sma_50']:
            lines.append(f"  SMA 50: {data['sma_50']}")

        return "\n".join(filter(None, lines))

    def _format_signal_html(self, signal: AlgorithmSignal) -> str:
        """Format signal as HTML email using template."""
        data = self._extract_signal_data(signal)

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: {data['signal_color']}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .metric {{ margin: 10px 0; }}
                .label {{ font-weight: bold; color: #666; }}
                .value {{ font-size: 1.2em; }}
                .rationale {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .levels {{ display: flex; gap: 20px; margin: 15px 0; }}
                .level {{ text-align: center; padding: 10px; background: #f8f9fa; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{data['signal_type']}: {data['ticker']}</h1>
                <p>{data['algorithm_name']} • Confidence: {data['confidence']}</p>
            </div>
            <div class="content">
                <div class="metric">
                    <span class="label">Current Price:</span>
                    <span class="value">{data['price']}</span>
                </div>
                <div class="rationale">
                    <strong>Rationale:</strong><br>
                    {data['rationale']}
                </div>
        """

        if data['has_levels']:
            html += '<div class="levels">'
            if data['has_entry']:
                html += f'<div class="level"><div class="label">Entry</div><div class="value">{data["entry"]}</div></div>'
            if data['has_stop']:
                html += f'<div class="level"><div class="label">Stop</div><div class="value">{data["stop"]}</div></div>'
            if data['has_target']:
                html += f'<div class="level"><div class="label">Target</div><div class="value">{data["target"]}</div></div>'
            html += '</div>'

        html += f"""
                <p style="color: #999; font-size: 0.9em; margin-top: 30px;">
                    Generated at {data['timestamp']}
                </p>
            </div>
        </body>
        </html>
        """

        return html

    def get_latest_signals(self) -> dict[str, dict[str, AlgorithmSignal]]:
        """Get current signal state for API access."""
        return self.state.last_signals.copy()


def create_alert_engine(
    smtp_user: str = "",
    smtp_password: str = "",
    to_emails: list[str] | None = None,
    min_confidence: float = 0.5,
) -> AlertEngine:
    """
    Factory function to create AlertEngine with common defaults.

    Args:
        smtp_user: Gmail address for sending
        smtp_password: Gmail app password
        to_emails: List of recipient emails
        min_confidence: Minimum signal confidence to alert on

    Returns:
        Configured AlertEngine
    """
    config = AlertConfig(
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        from_email=smtp_user,
        to_emails=to_emails or [],
        min_confidence=min_confidence,
    )
    return AlertEngine(config)
