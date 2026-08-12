from __future__ import annotations
import html
import json
from pathlib import Path
import platform
import sys
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QLineEdit, QPushButton, QLabel, QInputDialog, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QIcon, QPixmap

from peer import Peer


THEME = {
    "background": "#020617",
    "panel": "#151b2f",
    "panel_alt": "#0b1224",
    "border": "#005f73",
    "accent": "#00ffc6",
    "accent_dim": "rgba(0, 255, 198, 0.12)",
    "cyan": "#00bcd4",
    "text": "#cbd5e1",
    "heading": "#e2e8f0",
    "muted": "#94a3b8",
    "danger": "#ef6b73",
    "warning": "#ffd580",
}


class ChatUI(QWidget):
    # Signal to trigger verification dialog from main thread
    verify_requested = pyqtSignal(str)
    message_received = pyqtSignal(str, str)
    status_received = pyqtSignal(str, str)
    identity_received = pyqtSignal(str, str)
    peer_address_received = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CryptoChat - End-to-End Encrypted Messenger")
        self.resize(900, 600)
        self.setMinimumSize(760, 520)
        self.assets_dir = Path(__file__).with_name("Assets")
        self.logo_path = self.assets_dir / "netflow-favicon.png"
        if self.logo_path.exists():
            self.setWindowIcon(QIcon(str(self.logo_path)))

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        self.local_name = self.ask_local_name()

        # Left: conversations list
        self.sidebar_collapsed = False
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        left = QVBoxLayout(self.sidebar)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)
        self.contacts = QListWidget()
        self.contacts.setObjectName("conversationList")
        self.contacts.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        convo_controls = QHBoxLayout()
        convo_controls.setSpacing(8)
        self.btn_add_convo = QPushButton("+")
        self.btn_remove_convo = QPushButton("-")
        self.btn_add_convo.setObjectName("iconButton")
        self.btn_remove_convo.setObjectName("iconButton")
        self.btn_add_convo.setFixedSize(28, 28)
        self.btn_remove_convo.setFixedSize(28, 28)
        self.btn_add_convo.setToolTip("Add conversation")
        self.btn_remove_convo.setToolTip("Remove selected conversation")
        self.btn_toggle_sidebar = QPushButton("‹")
        self.btn_toggle_sidebar.setObjectName("iconButton")
        self.btn_toggle_sidebar.setFixedSize(28, 28)
        self.btn_toggle_sidebar.setToolTip("Collapse chats")

        self.conversations_label = QLabel("Chats")
        self.conversations_label.setObjectName("sectionLabel")
        convo_controls.addWidget(self.conversations_label)
        convo_controls.addStretch()
        convo_controls.addWidget(self.btn_add_convo)
        convo_controls.addWidget(self.btn_remove_convo)
        convo_controls.addWidget(self.btn_toggle_sidebar)
        left.addLayout(convo_controls)
        left.addWidget(self.contacts)

        # Right: chat + details
        right = QVBoxLayout()
        right.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(12)
        self.logo = QLabel()
        self.logo.setObjectName("logo")
        if self.logo_path.exists():
            self.logo.setPixmap(
                QPixmap(str(self.logo_path)).scaled(
                    42,
                    42,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        self.title = QLabel("CryptoChat")
        self.title.setObjectName("appTitle")
        self.subtitle = QLabel("End-to-End Encrypted Messenger")
        self.subtitle.setObjectName("appSubtitle")
        title_block.addWidget(self.title)
        title_block.addWidget(self.subtitle)
        header.addWidget(self.logo)
        header.addLayout(title_block)
        header.addStretch()

        self.status = QLabel("Status: idle")
        self.status.setObjectName("statusLabel")

        # Contact details panel (NOW with both fingerprints + state)
        self.details = QLabel()
        self.details.setObjectName("detailsPanel")
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details.setText(
            "Contact: -<br>"
            "Last IP: -<br>"
            "Local FP: -<br>"
            "Peer FP: -<br>"
            "Trust: <span style='color: gray;'>unverified</span><br>"
            "Connection: <span style='color: gray;'>idle</span>"
        )

        self.view = QListWidget()
        self.view.setObjectName("chatView")
        self.view.setSpacing(6)
        self.input = QLineEdit()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("Type an encrypted message…")
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primaryButton")
        self.send_btn.setFixedWidth(110)

        self.btn_server = QPushButton("Listen")
        self.btn_client = QPushButton("Connect")
        self.btn_reset_trust = QPushButton("Reset Trust")
        self.btn_server.setObjectName("secondaryButton")
        self.btn_client.setObjectName("secondaryButton")
        self.btn_reset_trust.setObjectName("dangerButton")

        right.addLayout(header)
        right.addWidget(self.status)
        right.addWidget(self.details)
        right.addWidget(self.view, stretch=1)

        composer = QHBoxLayout()
        composer.setSpacing(10)
        composer.addWidget(self.input, stretch=1)
        composer.addWidget(self.send_btn)
        right.addLayout(composer)

        connection_actions = QHBoxLayout()
        connection_actions.setSpacing(10)
        connection_actions.addWidget(self.btn_server)
        connection_actions.addWidget(self.btn_client)
        connection_actions.addWidget(self.btn_reset_trust)
        right.addLayout(connection_actions)

        root.addWidget(self.sidebar)
        root.addLayout(right, 3)
        self.apply_theme()

        # === Multi-contact state ===
        self.peers: Dict[str, Peer] = {}
        self.histories: Dict[str, list[str]] = {}
        # contact_info[name] = {last_ip, fingerprint, peer_fp, state, fingerprint_verified}
        self.contact_info: Dict[str, dict] = {}
        self.contact_aliases: Dict[str, str] = {}
        self.current_contact: Optional[str] = None
        self.unknown_counter = 0
        self.legacy_trust_path = Path(__file__).with_name("trusted_contacts.json")
        self.trust_paths = self.default_trust_save_paths()
        self.trust_path = self.trust_paths[0]
        self.trusted_fingerprints = self.load_trusted_contacts()

        # Wire up signals
        self.contacts.currentItemChanged.connect(self.on_contact_item_selected)
        self.btn_add_convo.clicked.connect(self.add_conversation)
        self.btn_remove_convo.clicked.connect(self.remove_current_conversation)
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        self.send_btn.clicked.connect(self.on_send)
        self.btn_server.clicked.connect(self.on_server)
        self.btn_client.clicked.connect(self.on_client)
        self.btn_reset_trust.clicked.connect(self.on_reset_trust)
        self.input.returnPressed.connect(self.on_send)
        self.verify_requested.connect(self.show_verify_dialog)
        self.message_received.connect(self.on_peer_message)
        self.status_received.connect(self.on_peer_status)
        self.identity_received.connect(self.on_peer_identity)
        self.peer_address_received.connect(self.on_peer_address)

        self.add_conversation()

    def ask_local_name(self) -> str:
        """Ask for the display name sent to peers after the encrypted handshake."""
        name, ok = QInputDialog.getText(
            self,
            "Your name",
            "Display name for this CryptoChat session:",
            text="Anonymous",
        )
        if not ok or not name.strip():
            return "Anonymous"
        return name.strip()[:80]

    def apply_theme(self):
        """Apply the portfolio color system to the PyQt interface."""
        self.setStyleSheet(f"""
            QWidget {{
                background: {THEME["background"]};
                color: {THEME["text"]};
                font-family: Arial, sans-serif;
                font-size: 13px;
            }}

            QLabel#appTitle {{
                color: {THEME["heading"]};
                font-size: 24px;
                font-weight: 700;
                letter-spacing: 0px;
            }}

            QLabel#appSubtitle,
            QLabel#sectionLabel {{
                color: {THEME["accent"]};
                font-size: 12px;
                font-weight: 600;
            }}

            QWidget#sidebar {{
                background: transparent;
            }}

            QLabel#statusLabel {{
                background: {THEME["panel_alt"]};
                border: 1px solid rgba(0, 255, 198, 0.20);
                border-radius: 8px;
                color: {THEME["text"]};
                padding: 9px 12px;
            }}

            QLabel#detailsPanel {{
                background: {THEME["panel"]};
                border: 1px solid rgba(0, 95, 115, 0.85);
                border-radius: 8px;
                color: {THEME["muted"]};
                font-size: 11px;
                padding: 12px;
            }}

            QListWidget#conversationList {{
                background: {THEME["panel"]};
                border: 1px solid rgba(0, 95, 115, 0.85);
                border-radius: 8px;
                color: {THEME["text"]};
                padding: 6px;
                outline: 0;
            }}

            QListWidget#conversationList::item {{
                border-radius: 6px;
                margin: 2px;
                padding: 4px;
            }}

            QListWidget#conversationList::item:selected {{
                background: {THEME["accent_dim"]};
                border: 1px solid rgba(0, 255, 198, 0.45);
                color: {THEME["heading"]};
            }}

            QListWidget#chatView {{
                background: {THEME["panel_alt"]};
                border: 1px solid rgba(0, 95, 115, 0.85);
                border-radius: 8px;
                color: {THEME["text"]};
                padding: 10px;
                outline: 0;
                selection-background-color: rgba(0, 255, 198, 0.30);
            }}

            QListWidget#chatView::item {{
                border: 0;
                padding: 2px;
                background: transparent;
            }}

            QListWidget#chatView::item:selected {{
                background: transparent;
            }}

            QLabel#incomingBubble {{
                background: {THEME["panel"]};
                border: 1px solid rgba(0, 95, 115, 0.90);
                border-radius: 8px;
                color: {THEME["heading"]};
                padding: 10px 13px;
                line-height: 1.35;
            }}

            QLabel#outgoingBubble {{
                background: #043f3f;
                border: 1px solid rgba(0, 255, 198, 0.80);
                border-radius: 8px;
                color: {THEME["heading"]};
                padding: 10px 13px;
                line-height: 1.35;
            }}

            QLineEdit#messageInput {{
                background: {THEME["panel"]};
                border: 1px solid rgba(0, 95, 115, 0.85);
                border-radius: 8px;
                color: {THEME["heading"]};
                padding: 11px 12px;
                selection-background-color: rgba(0, 255, 198, 0.30);
            }}

            QLineEdit#messageInput:focus {{
                border-color: {THEME["accent"]};
            }}

            QPushButton {{
                border-radius: 8px;
                font-weight: 700;
                min-height: 34px;
                padding: 8px 12px;
            }}

            QPushButton#primaryButton {{
                background: {THEME["accent"]};
                border: 1px solid {THEME["accent"]};
                color: {THEME["background"]};
            }}

            QPushButton#iconButton {{
                max-height: 28px;
                min-height: 28px;
                min-width: 28px;
                max-width: 28px;
                border-radius: 6px;
                font-size: 14px;
                padding: 0;
            }}

            QPushButton#secondaryButton,
            QPushButton#iconButton {{
                background: transparent;
                border: 1px solid {THEME["accent"]};
                color: {THEME["accent"]};
            }}

            QPushButton#dangerButton {{
                background: transparent;
                border: 1px solid rgba(239, 107, 115, 0.75);
                color: {THEME["danger"]};
            }}

            QPushButton:hover {{
                background: {THEME["accent_dim"]};
            }}

            QPushButton#primaryButton:hover {{
                background: #38ffd3;
            }}

            QScrollBar:vertical {{
                background: {THEME["background"]};
                width: 10px;
                margin: 0;
            }}

            QScrollBar::handle:vertical {{
                background: {THEME["border"]};
                border-radius: 5px;
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

    # ---------- Contact / Session Management ----------

    def conversation_name_from_item(self, item: QListWidgetItem | None) -> str:
        if item is None:
            return ""
        return item.data(Qt.ItemDataRole.UserRole) or item.text()

    def on_contact_item_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Switch active chat when a conversation row is selected."""
        self.on_contact_selected(self.conversation_name_from_item(current))

    def on_contact_selected(self, name: str):
        """Switch active chat to the selected contact."""
        if not name:
            return
        self.current_contact = name
        self.histories.setdefault(name, [])
        self.contact_info.setdefault(name, {})
        self.view.clear()
        for entry in self.histories[name]:
            if isinstance(entry, dict):
                self.add_message_bubble(entry["sender"], entry["msg"], entry["own"])
        self.status.setText(f"Status [{name}]: idle")
        self.update_contact_details(name)
        self.refresh_all_conversations()

    def get_or_create_peer(self, name: str) -> Peer:
        """Get or create a Peer object bound to a specific contact."""

        if name in self.peers:
            return self.peers[name]

        def on_msg(msg: str, contact=name):
            self.message_received.emit(contact, msg)

        def on_status(text: str, contact=name):
            self.status_received.emit(contact, text)

        def on_identity(display_name: str, contact=name):
            self.identity_received.emit(contact, display_name)

        def on_peer_address(address: str, contact=name):
            self.peer_address_received.emit(contact, address)

        p = Peer(
            on_message=on_msg,
            on_status=on_status,
            on_identity=on_identity,
            on_peer_address=on_peer_address,
            local_name=self.local_name,
        )
        self.peers[name] = p
        self.histories.setdefault(name, [])
        info = self.contact_info.setdefault(name, {})

        # Store local fingerprint for that contact/session
        try:
            fp = p.sess.fingerprint()
        except Exception:
            fp = "-"
        info.setdefault("fingerprint", fp)

        if self.current_contact == name:
            self.update_contact_details(name)

        return p

    def add_conversation(self):
        """Add a new empty conversation that will be renamed after identity exchange."""
        self.unknown_counter += 1
        name = self.unique_conversation_name("Unknown")
        self.add_conversation_item(name)
        self.histories.setdefault(name, [])
        self.contact_info.setdefault(name, {})
        self.contacts.setCurrentRow(self.contacts.count() - 1)

    def remove_current_conversation(self):
        """Remove the selected conversation and close its peer connection."""
        row = self.contacts.currentRow()
        if row < 0:
            return

        item = self.contacts.item(row)
        name = self.conversation_name_from_item(item)
        peer = self.peers.pop(name, None)
        if peer:
            peer.close()
        self.histories.pop(name, None)
        self.contact_info.pop(name, None)
        self.contacts.takeItem(row)

        if self.contacts.count() == 0:
            self.current_contact = None
            self.view.clear()
            self.status.setText("Status: no conversations")
            self.details.setText(
                "Contact: -<br>"
                f"Your Name: {html.escape(self.local_name)}<br>"
                "Last IP: -<br>"
                "Local FP: -<br>"
                "Peer FP: -<br>"
                "Trust: <span style='color: gray;'>unverified</span><br>"
                "Connection: <span style='color: gray;'>idle</span>"
            )
        else:
            self.contacts.setCurrentRow(min(row, self.contacts.count() - 1))

    def add_conversation_item(self, name: str):
        """Add a conversation row with a colored status dot."""
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setSizeHint(QSize(64 if self.sidebar_collapsed else 120, 42))
        self.contacts.addItem(item)
        self.refresh_conversation_item(name)

    def refresh_conversation_item(self, name: str):
        """Refresh one conversation row's status dot and label."""
        for i in range(self.contacts.count()):
            item = self.contacts.item(i)
            if self.conversation_name_from_item(item) != name:
                continue

            selected = self.current_contact == name
            row = QWidget()
            row.setObjectName("conversationRow")
            layout = QHBoxLayout(row)
            if self.sidebar_collapsed:
                layout.setContentsMargins(5, 6, 5, 6)
                layout.setSpacing(4)
            else:
                layout.setContentsMargins(8, 6, 8, 6)
                layout.setSpacing(8)
            if selected:
                row.setStyleSheet(
                    "QWidget#conversationRow { "
                    "background: rgba(0, 255, 198, 0.12); "
                    "border: 1px solid rgba(0, 255, 198, 0.45); "
                    "border-radius: 6px; }"
                    "QLabel { background: transparent; }"
                )
            else:
                row.setStyleSheet(
                    "QWidget#conversationRow { "
                    "background: rgba(2, 6, 23, 0.55); "
                    "border: 1px solid transparent; "
                    "border-radius: 6px; }"
                    "QLabel { background: transparent; }"
                )

            dot = QLabel("●")
            dot.setFixedWidth(8 if self.sidebar_collapsed else 12)
            dot.setStyleSheet(
                f"color: {self.conversation_dot_color(name)}; "
                f"font-size: {10 if self.sidebar_collapsed else 13}px;"
            )

            display_name = self.conversation_display_name(name)
            label = QLabel(display_name)
            label.setObjectName("conversationName")
            label.setStyleSheet(
                f"color: {THEME['heading']}; font-weight: 700; "
                f"font-size: {12 if self.sidebar_collapsed else 13}px;"
            )
            label.setToolTip(name)
            if self.sidebar_collapsed:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setFixedWidth(26)

            layout.addWidget(dot)
            layout.addWidget(label, stretch=1)
            self.contacts.setItemWidget(item, row)
            item.setSizeHint(QSize(58 if self.sidebar_collapsed else 120, 42))
            return

    def refresh_all_conversations(self):
        """Refresh all conversation rows."""
        for i in range(self.contacts.count()):
            self.refresh_conversation_item(self.conversation_name_from_item(self.contacts.item(i)))

    def conversation_display_name(self, name: str) -> str:
        """Return full names when expanded and initials when collapsed."""
        if not self.sidebar_collapsed:
            return name

        parts = [part for part in name.replace("-", " ").split() if part]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][0].upper()
        return "".join(part[0].upper() for part in parts[:2])

    def conversation_dot_color(self, name: str) -> str:
        """Return status-dot color for the conversation list."""
        info = self.contact_info.get(name, {})
        state = (info.get("state") or "").lower()
        if "disconnected" in state or "closed" in state:
            return THEME["danger"]
        if info.get("fingerprint_mismatch") or "error" in state or "warning" in state:
            return THEME["danger"]
        if info.get("fingerprint_verified"):
            return THEME["accent"]
        if "listening" in state or "starting" in state or "connecting" in state:
            return THEME["warning"]
        if "session key established" in state or "connected" in state:
            return THEME["warning"]
        return THEME["muted"]

    def toggle_sidebar(self):
        """Collapse/expand the conversation panel to prioritize chat width."""
        self.sidebar_collapsed = not self.sidebar_collapsed
        if self.sidebar_collapsed:
            self.sidebar.setFixedWidth(78)
            self.conversations_label.setText("")
            self.btn_add_convo.hide()
            self.btn_remove_convo.hide()
            self.conversations_label.hide()
            self.btn_toggle_sidebar.setText("›")
            self.btn_toggle_sidebar.setToolTip("Expand chats")
        else:
            self.sidebar.setFixedWidth(240)
            self.conversations_label.setText("Chats")
            self.conversations_label.show()
            self.btn_add_convo.show()
            self.btn_remove_convo.show()
            self.btn_toggle_sidebar.setText("‹")
            self.btn_toggle_sidebar.setToolTip("Collapse chats")
        self.refresh_all_conversations()

    def unique_conversation_name(self, desired: str, current: str | None = None) -> str:
        """Return a display name that does not collide with another conversation."""
        base = desired.strip()[:80] or "Unknown"
        existing = {
            self.conversation_name_from_item(self.contacts.item(i))
            for i in range(self.contacts.count())
            if self.conversation_name_from_item(self.contacts.item(i)) != current
        }
        if base not in existing:
            return base

        idx = 2
        while f"{base} ({idx})" in existing:
            idx += 1
        return f"{base} ({idx})"

    def rename_conversation(self, old_name: str, new_name: str) -> str:
        """Rename conversation state after the peer sends its display name."""
        if old_name not in self.contact_info:
            return old_name

        final_name = self.unique_conversation_name(new_name, current=old_name)
        if final_name == old_name:
            return old_name

        self.contact_info[final_name] = self.contact_info.pop(old_name)
        self.histories[final_name] = self.histories.pop(old_name, [])
        if old_name in self.peers:
            self.peers[final_name] = self.peers.pop(old_name)

        for i in range(self.contacts.count()):
            item = self.contacts.item(i)
            if self.conversation_name_from_item(item) == old_name:
                item.setData(Qt.ItemDataRole.UserRole, final_name)
                self.refresh_conversation_item(final_name)
                break

        if self.current_contact == old_name:
            self.current_contact = final_name
        self.contact_aliases[old_name] = final_name
        return final_name

    def resolve_contact(self, contact: str) -> str:
        """Resolve callback names after a conversation has been renamed."""
        while contact in self.contact_aliases:
            contact = self.contact_aliases[contact]
        return contact

    # ---------- UI Helpers ----------

    def _state_color(self, state: str) -> str:
        """Map connection state text to a color (strict matching)."""
        s = (state or "").lower()
        if "disconnected" in s or "closed" in s:
            return "red"
        if "error" in s or "warning" in s or "mismatch" in s:
            return "red"
        if "verified" in s:
            return "green"
        if "session key established" in s or "connected" in s:
            return "green"
        if "listening" in s or "starting" in s or "connecting" in s:
            return "orange"
        return "gray"

    def _trust_label(self, info: dict) -> tuple[str, str]:
        if info.get("fingerprint_mismatch"):
            return "fingerprint mismatch - sending blocked", THEME["danger"]
        if info.get("fingerprint_verified"):
            return "verified", THEME["accent"]
        return "unverified - sending blocked", THEME["warning"]

    def add_message_bubble(self, sender: str, msg: str, own: bool = False):
        """Add an iMessage-style bubble aligned by sender."""
        row = QWidget()
        row.setObjectName("messageRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(0)
        row.setStyleSheet("QWidget#messageRow { background: transparent; }")

        bubble = QLabel()
        bubble.setObjectName("outgoingBubble" if own else "incomingBubble")
        bubble.setTextFormat(Qt.TextFormat.RichText)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setWordWrap(True)
        bubble.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        max_width = max(260, int(self.view.viewport().width() * 0.68))

        sender_color = THEME["accent"] if own else THEME["cyan"]
        bubble_width = min(max_width, self.message_text_width(bubble, sender, msg))
        bubble.setFixedWidth(bubble_width)
        bubble.setText(
            f"<div style='font-size:11px; font-weight:700; color:{sender_color}; "
            f"margin-bottom:4px;'>{html.escape(sender)}</div>"
            f"<div style='font-size:13px;'>{html.escape(msg)}</div>"
        )
        bubble.adjustSize()

        if own:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)

        item = QListWidgetItem()
        self.view.addItem(item)
        self.view.setItemWidget(item, row)
        row.adjustSize()
        hint = row.sizeHint()
        item.setSizeHint(QSize(hint.width(), hint.height() + 10))
        self.view.scrollToBottom()

    def message_entry(self, sender: str, msg: str, own: bool = False) -> dict:
        return {"sender": sender, "msg": msg, "own": own}

    def message_text_width(self, bubble: QLabel, sender: str, msg: str) -> int:
        """Estimate a bubble width that follows the text without growing full-row."""
        metrics = QFontMetrics(bubble.font())
        lines = [sender] + (msg.splitlines() or [""])
        longest = max(metrics.horizontalAdvance(line) for line in lines)
        return max(96, longest + 58)

    def update_contact_details(self, name: str):
        """Refresh the details panel for the selected contact."""
        info = self.contact_info.get(name, {})
        ip = info.get("last_ip", "-")
        local_fp = info.get("fingerprint", "-")
        peer_fp = info.get("peer_fp", "-")
        state = info.get("state", "idle")
        color = self._state_color(state)
        state_disp = state or "idle"
        trust_disp, trust_color = self._trust_label(info)


        self.details.setText(
            f"Contact: {html.escape(name)}<br>"
            f"Your Name: {html.escape(self.local_name)}<br>"
            f"Last IP: {html.escape(ip)}<br>"
            f"Local FP: {html.escape(local_fp)}<br>"
            f"Peer FP: {html.escape(peer_fp)}<br>"
            f"Trust: <span style='color: {trust_color};'>{html.escape(trust_disp)}</span><br>"
            f"Connection: <span style='color: {color};'>{html.escape(state_disp)}</span>"
        )

    def default_trust_save_paths(self) -> list[Path]:
        """Return user-owned candidate locations for local TOFU trust state."""
        paths = []
        if platform.system() == "Darwin":
            paths.append(
                Path.home()
                / "Library"
                / "Application Support"
                / "CryptoChat"
                / "trusted_contacts.json"
            )
        else:
            paths.append(Path.home() / ".cryptochat" / "trusted_contacts.json")
        paths.append(Path.home() / ".cryptochat" / "trusted_contacts.json")
        return list(dict.fromkeys(paths))

    def _read_trust_file(self, path: Path) -> dict[str, str]:
        """Read a trust JSON file if it exists and has the expected shape."""
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except Exception:
            return {}

        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def load_trusted_contacts(self) -> dict[str, str]:
        """Load local TOFU trust state."""
        for path in self.trust_paths:
            trusted = self._read_trust_file(path)
            if trusted:
                self.trust_path = path
                return trusted

        trusted = self._read_trust_file(self.legacy_trust_path)
        if trusted:
            return trusted
        return {}

    def save_trusted_contacts(self) -> bool:
        """Persist local TOFU trust state."""
        last_error = None
        for path in self.trust_paths:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8") as f:
                    json.dump(self.trusted_fingerprints, f, indent=2, sort_keys=True)
                self.trust_path = path
                return True
            except Exception as e:
                last_error = e

        self.status.setText(f"Status: could not save trust store: {last_error}")
        QMessageBox.warning(
            self,
            "Trust store not saved",
            f"CryptoChat could not save trusted fingerprints:\n{last_error}",
        )
        return False

    def apply_trust_policy(self, contact: str):
        """Apply TOFU trust checks after a peer fingerprint is known."""
        info = self.contact_info.setdefault(contact, {})
        peer_fp = info.get("peer_fp")
        if not peer_fp or peer_fp == "-":
            info["fingerprint_verified"] = False
            info["fingerprint_mismatch"] = False
            return

        trusted_fp = self.trusted_fingerprints.get(contact)
        if trusted_fp is None:
            info["fingerprint_verified"] = False
            info["fingerprint_mismatch"] = False
            self.verify_requested.emit(contact)
        elif trusted_fp == peer_fp:
            info["fingerprint_verified"] = True
            info["fingerprint_mismatch"] = False
            info["state"] = "Session key established (verified)"
        else:
            info["fingerprint_verified"] = False
            info["fingerprint_mismatch"] = True
            info["state"] = "WARNING: saved fingerprint does not match current peer"

    def send_block_reason(self, contact: str, peer: Peer | None) -> str | None:
        """Return a user-facing reason if sending should be blocked."""
        if peer is None or peer.sess.send_key is None:
            return "No encrypted session is active. Start or connect first."

        info = self.contact_info.get(contact, {})
        if info.get("fingerprint_mismatch"):
            return "Fingerprint mismatch. Sending is blocked until trust is reset and verified."
        if not info.get("fingerprint_verified"):
            return "Peer fingerprint is not verified. Verify it before sending."
        return None

    def on_peer_status(self, contact: str, text: str):
        """Update status when a Peer reports something."""
        contact = self.resolve_contact(contact)
        if contact not in self.contact_info:
            return
        info = self.contact_info.setdefault(contact, {})
        info["state"] = text
        display_text = text

        # When session key is established, capture peer fingerprint + TOFU prompt
        if "Session key established" in text:
            peer = self.peers.get(contact)
            if peer is not None:
                try:
                    peer_fp = peer.sess.peer_fingerprint()
                except Exception:
                    peer_fp = "-"
                info["peer_fp"] = peer_fp

                # Ensure local fingerprint stored
                if "fingerprint" not in info:
                    try:
                        info["fingerprint"] = peer.sess.fingerprint()
                    except Exception:
                        pass

                if info.get("remote_name"):
                    self.apply_trust_policy(contact)
                    display_text = info.get("state", text)
                else:
                    info["fingerprint_verified"] = False
                    info["fingerprint_mismatch"] = False
                    info["state"] = "Session key established; waiting for peer name"
                    display_text = info["state"]

        if self.current_contact == contact:
            self.status.setText(f"Status [{contact}]: {display_text}")
            self.update_contact_details(contact)
        self.refresh_conversation_item(contact)

    def on_peer_address(self, contact: str, address: str):
        """Store and display the remote IP address for either role."""
        contact = self.resolve_contact(contact)
        if contact not in self.contact_info:
            return
        info = self.contact_info.setdefault(contact, {})
        info["last_ip"] = address
        if self.current_contact == contact:
            self.update_contact_details(contact)

    def on_peer_identity(self, contact: str, display_name: str):
        """Handle encrypted display-name metadata from a peer."""
        contact = self.resolve_contact(contact)
        if contact not in self.contact_info:
            return

        new_contact = self.rename_conversation(contact, display_name)
        info = self.contact_info.setdefault(new_contact, {})
        info["remote_name"] = display_name
        info["state"] = "Peer name received"

        if info.get("peer_fp"):
            self.apply_trust_policy(new_contact)

        if self.current_contact == new_contact:
            self.status.setText(f"Status [{new_contact}]: {info.get('state', 'Peer name received')}")
            self.update_contact_details(new_contact)
        self.refresh_conversation_item(new_contact)

    def on_peer_message(self, contact: str, msg: str):
        """Handle incoming message for a specific contact."""
        contact = self.resolve_contact(contact)
        if contact not in self.contact_info:
            return
        entry = self.message_entry(contact, msg)
        self.histories.setdefault(contact, []).append(entry)
        if self.current_contact == contact:
            self.add_message_bubble(contact, msg)

    def show_verify_dialog(self, contact: str):
        """TOFU-style fingerprint verification dialog."""
        info = self.contact_info.setdefault(contact, {})
        local_fp = info.get("fingerprint", "-")
        peer_fp = info.get("peer_fp", "-")

        msg = QMessageBox(self)
        msg.setWindowTitle(f"Verify fingerprint for {contact}")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Verify key fingerprints with your peer over a trusted channel.")
        msg.setInformativeText(
            f"Contact: {contact}\n\n"
            f"Your fingerprint:\n{local_fp}\n\n"
            f"Peer fingerprint (as you see it here):\n{peer_fp}\n\n"
            f"Ask the other side to read their fingerprint out loud. Do they match?"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        res = msg.exec()

        if res == QMessageBox.StandardButton.Yes:
            info["fingerprint_verified"] = True
            info["fingerprint_mismatch"] = False
            self.trusted_fingerprints[contact] = peer_fp
            if self.save_trusted_contacts():
                info["state"] = "Session key established (verified)"
            else:
                self.trusted_fingerprints.pop(contact, None)
                info["state"] = "Session verified for now; trust was not saved"
        else:
            info["fingerprint_verified"] = False
            info["fingerprint_mismatch"] = False
            info["state"] = "WARNING: fingerprint not verified"

        if self.current_contact == contact:
            self.update_contact_details(contact)
            self.status.setText(f"Status [{contact}]: {info['state']}")
        self.refresh_conversation_item(contact)

    def on_reset_trust(self):
        """Remove the saved fingerprint for the selected contact."""
        if not self.current_contact:
            self.status.setText("Status: Select a contact first.")
            return

        contact = self.current_contact
        res = QMessageBox.question(
            self,
            f"Reset trust for {contact}",
            "Remove the saved fingerprint for this contact?",
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        self.trusted_fingerprints.pop(contact, None)
        self.save_trusted_contacts()
        info = self.contact_info.setdefault(contact, {})
        info["fingerprint_verified"] = False
        info["fingerprint_mismatch"] = False
        info["state"] = "Trust reset; verify fingerprint before sending"

        self.update_contact_details(contact)
        self.status.setText(f"Status [{contact}]: {info['state']}")
        self.refresh_conversation_item(contact)
        if info.get("peer_fp") and info.get("peer_fp") != "-":
            self.verify_requested.emit(contact)

    # ---------- Button Actions ----------

    def on_send(self):
        """Send a message to the currently selected contact."""
        text = self.input.text().strip()
        if not text:
            return
        if not self.current_contact:
            self.status.setText("Status: Select a contact first.")
            return

        name = self.current_contact
        peer = self.peers.get(name)
        block_reason = self.send_block_reason(name, peer)
        if block_reason:
            self.status.setText(f"Status [{name}]: {block_reason}")
            self.update_contact_details(name)
            return

        try:
            peer.send(text)
        except Exception as e:
            self.status.setText(f"Status [{name}]: send failed: {e}")
            return

        entry = self.message_entry("You", text, own=True)
        self.histories.setdefault(name, []).append(entry)
        if self.current_contact == name:
            self.add_message_bubble("You", text, own=True)
        self.input.clear()

    def on_server(self):
        """Start listening as server for the selected contact."""
        if not self.current_contact:
            self.status.setText("Status: Select a contact first.")
            return

        name = self.current_contact
        peer = self.get_or_create_peer(name)
        from threading import Thread

        info = self.contact_info.setdefault(name, {})
        info["state"] = "Starting server…"
        if self.current_contact == name:
            self.update_contact_details(name)
            self.status.setText(f"Status [{name}]: Starting server…")
        self.refresh_conversation_item(name)

        Thread(target=peer.start_server, daemon=True).start()

    def on_client(self):
        """Connect as client to the selected contact."""
        if not self.current_contact:
            self.status.setText("Status: Select a contact first.")
            return

        name = self.current_contact
        info = self.contact_info.setdefault(name, {})
        default_ip = info.get("last_ip", "127.0.0.1")

        host, ok = QInputDialog.getText(
            self,
            "Connect",
            f"Server IP for {name}:",
            text=default_ip,
        )
        if not ok or not host:
            return

        info["last_ip"] = host
        peer = self.get_or_create_peer(name)
        from threading import Thread

        info["state"] = f"Connecting to {host}…"
        if self.current_contact == name:
            self.update_contact_details(name)
            self.status.setText(f"Status [{name}]: Connecting to {host}…")
        self.refresh_conversation_item(name)

        Thread(target=peer.start_client, kwargs={"host": host}, daemon=True).start()

    # ---------- Misc ----------

    def closeEvent(self, e):
        """Close all peers on exit."""
        try:
            for p in self.peers.values():
                p.close()
        finally:
            return super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = ChatUI()
    ui.show()
    sys.exit(app.exec())
