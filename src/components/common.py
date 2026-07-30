"""Small reusable presentation components shared across views."""

from src.html_utils import esc, render_html


def metric_card(label, value, detail, icon):
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-top">
                <span class="metric-icon">{icon}</span>
                <span class="metric-label">{esc(label)}</span>
            </div>
            <div class="metric-value">{esc(value)}</div>
            <div class="metric-detail">{esc(detail)}</div>
        </div>
        """
    )


def section_header(eyebrow, title, description=""):
    render_html(
        f"""
        <div class="section-heading">
            <div class="eyebrow">{esc(eyebrow)}</div>
            <h2>{esc(title)}</h2>
            <p>{esc(description)}</p>
        </div>
        """
    )


def topic_row(topic, accuracy_value, status):
    status_class = status.lower().replace(" ", "-")
    width = max(0, min(accuracy_value, 100))
    render_html(
        f"""
        <div class="topic-row">
            <div class="topic-row-top">
                <div>
                    <div class="topic-name">{esc(topic)}</div>
                    <div class="topic-status {status_class}">{esc(status)}</div>
                </div>
                <div class="topic-score">{accuracy_value}%</div>
            </div>
            <div class="topic-progress-track">
                <div class="topic-progress-fill" style="width: {width}%;"></div>
            </div>
        </div>
        """
    )


def empty_state(message):
    render_html(
        f'<p style="color: var(--muted); font-size: 0.85rem; margin: 0.5rem 0;">{esc(message)}</p>'
    )
