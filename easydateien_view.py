#!/usr/bin/env python3
"""EasyDateien — Bildschirmaufbau: build_screen und Statusleiste.

Mixin; entstanden durch mechanischen Modul-Split. Nutzt die Helfer aus
easydateien_ui und die Zustandsattribute des Kerns.
"""

from easydateien_ui import (
    ANSI_ESCAPE_RE, C_BOLD, C_INVERT, C_RESET,
    List, build_help_items, build_modal_box, cell_inner_width,
    distribute_options, format_entry_name, format_mtime, format_size,
    frame_cell, get_file_type_desc, os, pad_to_width,
    render_input_field, replace_ansi_range, safe_text, scan_directory,
    str_width, truncate_name, truncate_to_width, key_display,
)

import os
from typing import Dict, List, Optional


class EasyDateienView:
    """Mixin: kompletter Bildschirmaufbau."""


    def build_screen(self, term_cols: int, term_rows: int) -> List[str]:
        """Baut den vollständigen Terminal-Bildschirm pixelgenau und flickerfrei auf."""
        # Automatische Aktualisierung der Dateiliste
        self.refresh_items()

        disp_path = self.get_short_dir(self.current_dir)
        total_items = len(self.items)
        cur_idx_str = f"{self.selected_idx + 1}/{total_items}" if total_items > 0 else "0/0"

        if self.status_message:
            msg_str = f" [{self.status_message}]"
        else:
            msg_str = ""

        right_header = (msg_str + "  " + cur_idx_str).strip() if msg_str else cur_idx_str
        right_header_plain = right_header

        avail_for_path = max(1, term_cols - str_width(right_header_plain) - 2)
        path_truncated = truncate_to_width(disp_path, avail_for_path)
        path_styled = path_truncated
        pad_space = " " * max(1, term_cols - str_width(path_styled) - str_width(right_header_plain))
        header_line = f"{path_styled}{pad_space}{right_header}"
        header_line = pad_to_width(header_line, term_cols)

        if term_rows <= 1:
            return [header_line]

        cur_item = self.items[self.selected_idx] if (self.items and 0 <= self.selected_idx < total_items) else None

        has_dialog = bool(self.active_dialog)
        has_status_bar = (term_rows >= 4)

        div_style = "alle"
        has_top_border = term_rows >= 4
        has_bottom_border = term_rows >= 4

        consumed = 1
        if has_top_border:
            consumed += 1
        if has_bottom_border:
            consumed += 1
        if has_status_bar:
            consumed += 1

        avail_total = max(1, term_rows - consumed)
        header_lines_count = 1 + (1 if has_top_border else 0)

        active_console = self.show_console or self.console_always_visible

        # Dynamische Berechnung der Konsolenhöhe: bis zu 30% der verfügbaren
        # Höhe, mindestens 2 und höchstens 16 Zeilen (immer aktiv; der Deckel
        # wirkt nur bei großen Fenstern, kleine Größen bleiben unverändert).
        if active_console:
            min_console_h = 2  # Mindesthöhe für die Konsole
            console_h = max(min_console_h, min(16, int(avail_total * 0.3)))
            # Prüfe ob genug Platz für Dateimanager bleibt
            min_fm_rows = 3  # Mindestens 3 Zeilen für Dateimanager
            if avail_total - console_h - 1 >= min_fm_rows:
                fm_rows = avail_total - console_h - 1
            else:
                # Nicht genug Platz - Konsole ausblenden (Dateimanager hat Priorität)
                console_h = 0
                fm_rows = avail_total
        else:
            console_h = 0
            fm_rows = avail_total

        eff_cols = self.get_effective_columns(term_cols)

        if eff_cols == 3:
            avail = max(10, term_cols - 4)
            w_left = max(5, int(avail * 0.16))
            w_right = max(10, int(avail * 0.33))
            w_mid = avail - w_left - w_right
            top_line = f"╭{'─' * w_left}┬{'─' * w_mid}┬{'─' * w_right}╮"
            bot_line = f"╰{'─' * w_left}┴{'─' * w_mid}┴{'─' * w_right}╯"
            mid_sep  = f"├{'─' * w_left}┴{'─' * w_mid}┴{'─' * w_right}┤"
        elif eff_cols == 2:
            avail = max(8, term_cols - 3)
            w_left = max(5, int(avail * 0.24))
            w_right = 0
            w_mid = avail - w_left
            top_line = f"╭{'─' * w_left}┬{'─' * w_mid}╮"
            bot_line = f"╰{'─' * w_left}┴{'─' * w_mid}╯"
            mid_sep  = f"├{'─' * w_left}┴{'─' * w_mid}┤"
        else:
            w_mid = max(4, term_cols - 2)
            w_left = 0
            w_right = 0
            top_line = f"╭{'─' * w_mid}╮"
            bot_line = f"╰{'─' * w_mid}╯"
            mid_sep  = f"├{'─' * w_mid}┤"

        parent_items = []
        cur_p_idx = 0
        if eff_cols >= 2:
            parent_path = os.path.dirname(self.current_dir)
            if parent_path != self.current_dir:
                if self.cached_parent_dir == parent_path and self.cached_parent_items:
                    parent_items = self.cached_parent_items
                else:
                    parent_items = scan_directory(
                        parent_path,
                        show_hidden=self.config.get("show_hidden", False),
                        sort_by=self.config.get("sort_by", "mtime"),
                        sort_reverse=self.config.get("sort_reverse", True),
                        sort_dir_first=self.config.get("sort_dir_first", True)
                    )
                    self.cached_parent_dir = parent_path
                    self.cached_parent_items = parent_items
                for i, pit in enumerate(parent_items):
                    if os.path.abspath(pit.path) == os.path.abspath(self.current_dir):
                        cur_p_idx = i
                        break

        p_start = 0 if len(parent_items) <= fm_rows else max(0, min(cur_p_idx - fm_rows // 2, len(parent_items) - fm_rows))
        m_start = 0 if total_items <= fm_rows else max(0, min(self.selected_idx - fm_rows // 2, total_items - fm_rows))

        child_items = []
        is_cur_dir = bool(cur_item and cur_item.is_dir)
        if eff_cols == 3 and cur_item and is_cur_dir:
            if self.cached_child_path == cur_item.path and self.cached_child_items:
                child_items = self.cached_child_items
            else:
                child_items = scan_directory(
                    cur_item.path,
                    show_hidden=self.config.get("show_hidden", False),
                    sort_by=self.config.get("sort_by", "mtime"),
                    sort_reverse=self.config.get("sort_reverse", True),
                    sort_dir_first=self.config.get("sort_dir_first", True)
                )
                self.cached_child_path = cur_item.path
                self.cached_child_items = child_items

        preview_lines = []
        if eff_cols == 3 and cur_item and not is_cur_dir:
            needed_p = max(1, fm_rows - 6)
            # Umbruch in der exakten Zellinnenbreite (w_right - 2): dann
            # passt jede umgebrochene Zeile ohne zweiten Schnitt, und es
            # erscheint kein sinnloses "..." am Zeilenende.
            preview_wrap_width = max(2, w_right - 2) if self.preview_wrap else None
            # Fenster ab Scroll-Offset laden: die Anzeige zeigt genau den
            # Bereich [offset, offset + bereich]; der Cache haelt die volle Datei.
            bereich = needed_p + max(0, self.preview_scroll_offset)
            preview_lines = self.load_file_preview_lines(cur_item.path, bereich, preview_wrap_width)

        self.last_layout = {
            "header_lines": header_lines_count, "avail_rows": fm_rows, "eff_cols": eff_cols,
            "div_style": div_style, "w_left": w_left, "w_mid": w_mid, "w_right": w_right,
            "m_start": m_start, "p_start": p_start, "active_console": active_console,
            "console_pos": "unten" if active_console else None,
            "split_row": (header_lines_count + fm_rows) if (active_console and console_h > 0) else -1,
            "child_items": child_items, "cur_item": cur_item, "is_cur_dir": is_cur_dir,
        }

        file_lines = []
        for r in range(fm_rows):
            sep_row = False
            if eff_cols >= 2:
                p_idx = p_start + r
                if p_idx < len(parent_items):
                    p_it = parent_items[p_idx]
                    is_act = (os.path.abspath(p_it.path) == os.path.abspath(self.current_dir))
                    p_in_cut = (self.clipboard_mode == "cut" and p_it.path in self.clipboard_paths)
                    p_in_copy = (self.clipboard_mode == "copy" and p_it.path in self.clipboard_paths)
                    p_is_sel = p_it.path in self.selected_paths
                    if p_in_cut:
                        p_b_char = f"{C_BOLD}×{C_RESET}"
                    elif p_in_copy:
                        p_b_char = f"{C_BOLD}+{C_RESET}"
                    elif p_is_sel:
                        p_b_char = f"{C_BOLD}*{C_RESET}"
                    else:
                        p_b_char = ""
                    prefix_char = f" {p_b_char} " if p_b_char else " "
                    if w_left >= 26:
                        p_styled = format_entry_name(p_it, max(3, w_left - str_width(prefix_char) - 1), bold=is_act or p_in_cut or p_in_copy or p_is_sel)
                        txt_l = f"{prefix_char}{p_styled}"
                        cell_left = pad_to_width(txt_l, w_left - 1) + " "
                    else:
                        p_styled = format_entry_name(p_it, max(2, w_left - str_width(prefix_char) - 1), bold=is_act or p_in_cut or p_in_copy or p_is_sel)
                        txt_l = f"{prefix_char}{p_styled}"
                        cell_left = pad_to_width(txt_l, w_left - 1) + " "
                    if is_act:
                        cell_left = f"{C_BOLD}{C_INVERT}{ANSI_ESCAPE_RE.sub('', cell_left)}{C_RESET}"
                else:
                    cell_left = " " * w_left
            else:
                cell_left = ""

            m_idx = m_start + r
            is_cur_row = False
            if m_idx < len(self.items):
                it = self.items[m_idx]
                is_cur = (m_idx == self.selected_idx)
                is_cur_row = is_cur
                is_sel = it.path in self.selected_paths
                in_cut = (self.clipboard_mode == "cut" and it.path in self.clipboard_paths)
                in_copy = (self.clipboard_mode == "copy" and it.path in self.clipboard_paths)

                if in_cut:
                    b_char = f"{C_BOLD}×{C_RESET}"
                elif in_copy:
                    b_char = f"{C_BOLD}+{C_RESET}"
                elif is_sel:
                    b_char = f"{C_BOLD}*{C_RESET}"
                else:
                    b_char = ""
                prefix_str = f"{b_char} " if b_char else ""
                prefix_len = str_width(prefix_str)
                s_str = format_size(it.size) if not it.is_dir else ""
                avail = cell_inner_width(w_mid)
                if s_str:
                    size_field = str_width(s_str)
                    avail_n = max(3, avail - prefix_len - size_field - 1)
                    n_styled = format_entry_name(it, avail_n, bold=is_cur or in_cut or in_copy or is_sel)
                    n_w = str_width(ANSI_ESCAPE_RE.sub("", n_styled))
                    body = prefix_str + n_styled + " " * max(1, avail - prefix_len - n_w - size_field - 1)
                    cell_mid = frame_cell(body + f"{s_str:>{size_field}}", w_mid)
                else:
                    avail_n = max(2, avail - prefix_len)
                    n_styled = format_entry_name(it, avail_n, bold=is_cur or in_cut or in_copy or is_sel)
                    cell_mid = frame_cell(prefix_str + n_styled, w_mid)
            elif len(self.items) == 0 and r == 0:
                cell_mid = frame_cell("(leer)", w_mid)
            else:
                cell_mid = " " * w_mid

            if eff_cols == 3:
                if cur_item and is_cur_dir:
                    if r < len(child_items):
                        c_it = child_items[r]
                        c_size = format_size(c_it.size) if not c_it.is_dir else ""
                        c_in_cut = (self.clipboard_mode == "cut" and c_it.path in self.clipboard_paths)
                        c_in_copy = (self.clipboard_mode == "copy" and c_it.path in self.clipboard_paths)
                        c_is_sel = c_it.path in self.selected_paths
                        if c_in_cut:
                            c_b_char = f"{C_BOLD}×{C_RESET}"
                        elif c_in_copy:
                            c_b_char = f"{C_BOLD}+{C_RESET}"
                        elif c_is_sel:
                            c_b_char = f"{C_BOLD}*{C_RESET}"
                        else:
                            c_b_char = ""
                        if w_right >= 26 and c_size:
                            c_field = str_width(c_size)
                            c_pre = f" {c_b_char} " if c_b_char else " "
                            name_w = max(3, w_right - str_width(c_pre) - c_field - 2)
                            c_styled = format_entry_name(c_it, name_w, bold=c_in_cut or c_in_copy or c_is_sel)
                            s_part = f" {c_size:>{c_field}} "
                            cell_right = pad_to_width(f"{c_pre}{c_styled}", w_right - c_field - 2) + s_part
                        elif w_right >= 26:
                            c_pre = f" {c_b_char} " if c_b_char else " "
                            name_w = max(3, w_right - str_width(c_pre) - 1)
                            c_styled = format_entry_name(c_it, name_w, bold=c_in_cut or c_in_copy or c_is_sel)
                            cell_right = pad_to_width(f"{c_pre}{c_styled}", w_right - 1) + " "
                        else:
                            c_pre = f" {c_b_char} " if c_b_char else " "
                            name_w = max(3, w_right - str_width(c_pre) - 1)
                            c_styled = format_entry_name(c_it, name_w, bold=c_in_cut or c_in_copy or c_is_sel)
                            cell_right = pad_to_width(f"{c_pre}{c_styled}", w_right - 1) + " "
                    elif len(child_items) == 0 and r == 0:
                        cell_right = pad_to_width(f" (leer)", w_right)
                    else:
                        cell_right = " " * w_right
                elif cur_item and not is_cur_dir:
                    size_str = format_size(cur_item.size)
                    date_str = format_mtime(cur_item.mtime, max(6, w_right - 11))
                    mode_str = cur_item.mode_str
                    card = [
                        f"{C_BOLD}Details{C_RESET}",
                        f"{'Typ:':<9}{truncate_to_width(get_file_type_desc(cur_item), max(3, w_right - 11))}",
                        f"{'Größe:':<9}{truncate_to_width(size_str, max(3, w_right - 11))}",
                        f"{'Datum:':<9}{truncate_to_width(date_str, max(3, w_right - 11))}",
                        f"{'Rechte:':<9}{truncate_to_width(mode_str, max(3, w_right - 11))}",
                    ]
                    if cur_item.is_symlink:
                        card.append(f"{'Ziel:':<9}{truncate_to_width(cur_item.symlink_target, max(3, w_right - 11))}")

                    if r < len(card):
                        cell_right = f" {pad_to_width(card[r], w_right - 2)} "
                    elif r == len(card) and fm_rows >= 10:
                        # Trennlinie nur in der rechten Spalte (Trenner vor der Vorschau)
                        cell_right = "─" * w_right
                        sep_row = True
                    else:
                        p_line_idx = r - (len(card) + 1) if fm_rows >= 10 else -1
                        if p_line_idx == 0 and self.preview_scroll_item != (cur_item.path if cur_item else None):
                            self.preview_scroll_offset = 0
                            self.preview_scroll_item = cur_item.path if cur_item else None
                        p_line_idx += self.preview_scroll_offset
                        if 0 <= p_line_idx < len(preview_lines) and p_line_idx >= self.preview_scroll_offset:
                            p_txt = preview_lines[p_line_idx]
                            if self.preview_wrap and preview_wrap_width:
                                cell_right = f" {pad_to_width(p_txt, max(2, w_right - 2))} "
                            else:
                                cell_right = f" {pad_to_width(truncate_to_width(p_txt, max(2, w_right - 2)), w_right - 2)} "
                        else:
                            cell_right = " " * w_right
                else:
                    cell_right = " " * w_right
            else:
                cell_right = ""

            if sep_row:
                # Trennlinie nur in der rechten Spalte: links mit ├ an den
                # Spaltentrenner angebunden, rechts ┤ am äusseren Rand
                j_edge_l = "│"
                j_edge_r = "┤"
                j_in_lm = "│"
                j_in_mr = "├"
                g_lm = g_mr = "  "
            else:
                j_edge_l = j_edge_r = j_in_lm = j_in_mr = "│"
                g_lm = g_mr = "  "

            if True:
                if eff_cols == 3:
                    row_line = f"{j_edge_l}{cell_left}{j_in_lm}{cell_mid}{j_in_mr}{cell_right}{j_edge_r}"
                elif eff_cols == 2:
                    row_line = f"│{cell_left}│{cell_mid}│"
                else:
                    row_line = f"│{cell_mid}│"

            if is_cur_row and cell_mid:
                inv_mid = f"{C_BOLD}{C_INVERT}{ANSI_ESCAPE_RE.sub('', cell_mid)}{C_RESET}"
                row_line = row_line.replace(cell_mid, inv_mid, 1)
            file_lines.append(pad_to_width(row_line, term_cols))

        all_lines = [header_line]
        if has_top_border and top_line:
            all_lines.append(pad_to_width(top_line, term_cols))
        all_lines.extend(file_lines)

        if active_console and console_h > 0:
            all_lines.append(pad_to_width(mid_sep, term_cols))
            inner_cw = max(4, term_cols - 2)
            c_lines = self.get_console_display_lines(max(2, inner_cw - 2), console_h)
            for cl in c_lines:
                if True:
                    all_lines.append(f"│ {pad_to_width(cl, inner_cw - 2)} │")
                else:
                    all_lines.append(pad_to_width(cl, term_cols))
            if has_bottom_border:
                c_bot = f"╰{'─' * (term_cols - 2)}╯"
                if c_bot:
                    all_lines.append(pad_to_width(c_bot, term_cols))
        elif has_bottom_border and bot_line:
            all_lines.append(pad_to_width(bot_line, term_cols))

        if has_status_bar:
            if self.active_dialog:
                if self.active_dialog == "rename":
                    label = " Umbenennen: "
                    inp_w = max(1, term_cols - str_width(label))
                    disp_inp = render_input_field(self.dialog_input, self.dialog_cursor, inp_w)
                    field_w = min(str_width(safe_text(self.dialog_input)) + 1, inp_w)
                    disp_inp = pad_to_width(disp_inp, field_w)
                    left_str = f"{label}{disp_inp}"
                    avail_h = max(1, term_cols - str_width(left_str) - 2)
                    opts_full = [f"[Eingabe] Bestätigen", f"[{key_display(self.keymap, 'cancel', 'ESC')}] Zurück"]
                    _esc_d = key_display(self.keymap, 'cancel', 'ESC')
                    opts_short = ["[Eingabe]", f"[{_esc_d}]"]
                    opts_mini = [f"[{_esc_d}]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= avail_h:
                        hints = distribute_options(opts_full, avail_h)
                    elif sum(str_width(x) for x in opts_short) + 1 <= avail_h:
                        hints = distribute_options(opts_short, avail_h)
                    elif str_width(opts_mini[0]) <= avail_h:
                        hints = distribute_options(opts_mini, avail_h)
                    else:
                        hints = ""
                    st_line = pad_to_width(f"{left_str}  {hints}" if hints else left_str, term_cols)
                elif self.active_dialog == "new":
                    label = " Neu erstellen: "
                    inp_w = max(1, term_cols - str_width(label))
                    disp_inp = render_input_field(self.dialog_input, self.dialog_cursor, inp_w)
                    field_w = min(str_width(safe_text(self.dialog_input)) + 1, inp_w)
                    disp_inp = pad_to_width(disp_inp, field_w)
                    left_str = f"{label}{disp_inp}"
                    avail_h = max(1, term_cols - str_width(left_str) - 2)
                    opts_full = [f"[Eingabe] Erstellen", f"[{key_display(self.keymap, 'cancel', 'ESC')}] Zurück"]
                    _esc_d = key_display(self.keymap, 'cancel', 'ESC')
                    opts_short = ["[Eingabe]", f"[{_esc_d}]"]
                    opts_mini = [f"[{_esc_d}]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= avail_h:
                        hints = distribute_options(opts_full, avail_h)
                    elif sum(str_width(x) for x in opts_short) + 1 <= avail_h:
                        hints = distribute_options(opts_short, avail_h)
                    elif str_width(opts_mini[0]) <= avail_h:
                        hints = distribute_options(opts_mini, avail_h)
                    else:
                        hints = ""
                    st_line = pad_to_width(f"{left_str}  {hints}" if hints else left_str, term_cols)
                elif self.active_dialog == "search":
                    label = " Filtern/Suche: "
                    inp_w = max(1, term_cols - str_width(label))
                    disp_inp = render_input_field(self.dialog_input, self.dialog_cursor, inp_w)
                    field_w = min(str_width(safe_text(self.dialog_input)) + 1, inp_w)
                    disp_inp = pad_to_width(disp_inp, field_w)
                    left_str = f"{label}{disp_inp}"
                    avail_h = max(1, term_cols - str_width(left_str) - 2)
                    opts_full = [f"[Eingabe] Filtern", f"[{key_display(self.keymap, 'cancel', 'ESC')}] Zurück"]
                    _esc_d = key_display(self.keymap, 'cancel', 'ESC')
                    opts_short = ["[Eingabe]", f"[{_esc_d}]"]
                    opts_mini = [f"[{_esc_d}]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= avail_h:
                        hints = distribute_options(opts_full, avail_h)
                    elif sum(str_width(x) for x in opts_short) + 1 <= avail_h:
                        hints = distribute_options(opts_short, avail_h)
                    elif str_width(opts_mini[0]) <= avail_h:
                        hints = distribute_options(opts_mini, avail_h)
                    else:
                        hints = ""
                    st_line = pad_to_width(f"{left_str}  {hints}" if hints else left_str, term_cols)
                elif self.active_dialog == "goto_path":
                    label = " Pfad: "
                    inp_w = max(1, term_cols - str_width(label))
                    disp_inp = render_input_field(self.dialog_input, self.dialog_cursor, inp_w)
                    field_w = min(str_width(safe_text(self.dialog_input)) + 1, inp_w)
                    disp_inp = pad_to_width(disp_inp, field_w)
                    left_str = f"{label}{disp_inp}"
                    avail_h = max(1, term_cols - str_width(left_str) - 2)
                    opts_full = [f"[Eingabe] Wechseln", f"[{key_display(self.keymap, 'cancel', 'ESC')}] Zurück"]
                    _esc_d = key_display(self.keymap, 'cancel', 'ESC')
                    opts_short = ["[Eingabe]", f"[{_esc_d}]"]
                    opts_mini = [f"[{_esc_d}]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= avail_h:
                        hints = distribute_options(opts_full, avail_h)
                    elif sum(str_width(x) for x in opts_short) + 1 <= avail_h:
                        hints = distribute_options(opts_short, avail_h)
                    elif str_width(opts_mini[0]) <= avail_h:
                        hints = distribute_options(opts_mini, avail_h)
                    else:
                        hints = ""
                    st_line = pad_to_width(f"{left_str}  {hints}" if hints else left_str, term_cols)
                elif self.active_dialog == "trash_confirm":
                    targets_c = len(self.selected_paths) if self.selected_paths else 1
                    t_name = f"{targets_c} Elemente" if targets_c > 1 else f"„{cur_item.name if cur_item else ''}“"
                    opts_full = ["[y] Ja", "[n] Nein"]
                    opts_short = ["[y/n]"]
                    opts_mini = ["[y/n]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= term_cols - 2:
                        chosen_opts = opts_full
                    elif sum(str_width(x) for x in opts_short) + 1 <= term_cols - 2:
                        chosen_opts = opts_short
                    else:
                        chosen_opts = opts_mini
                    opts_w = sum(str_width(x) for x in chosen_opts) + max(0, len(chosen_opts) - 1) if chosen_opts else 0
                    avail_name = max(1, term_cols - 12 - opts_w)
                    # Erhalte Dateiendung in Dialog
                    if targets_c == 1 and cur_item:
                        t_trunc = truncate_name(cur_item.name, cur_item.is_dir, avail_name)
                        left_str = f" „{t_trunc}“ löschen?"
                    else:
                        t_trunc = truncate_to_width(t_name, avail_name)
                        left_str = f" {t_trunc} löschen?"
                    avail_right = max(0, term_cols - str_width(left_str) - 1)
                    if chosen_opts:
                        hints = " ".join(chosen_opts)
                        st_line = pad_to_width(f"{left_str} {hints}", term_cols)
                    else:
                        st_line = pad_to_width(left_str, term_cols)
                elif self.active_dialog == "overwrite_confirm":
                    if self.conflicts_to_resolve:
                        src, dest = self.conflicts_to_resolve[0]
                        file_name = os.path.basename(dest)
                        has_multiple = len(self.conflicts_to_resolve) > 1
                        if has_multiple:
                            opts_full = ["[y] Ja", "[n] Nein", "[a] Alle"]
                            opts_short = ["[y/n/a]"]
                            opts_mini = ["[y/n/a]"]
                        else:
                            opts_full = ["[y] Ja", "[n] Nein"]
                            opts_short = ["[y/n]"]
                            opts_mini = ["[y/n]"]
                        if sum(str_width(x) for x in opts_full) + 2 <= term_cols - 2:
                            chosen_opts = opts_full
                        elif sum(str_width(x) for x in opts_short) + 1 <= term_cols - 2:
                            chosen_opts = opts_short
                        else:
                            chosen_opts = opts_mini
                        opts_w = sum(str_width(x) for x in chosen_opts) + max(0, len(chosen_opts) - 1) if chosen_opts else 0
                        avail_name = max(1, term_cols - 12 - opts_w)
                        # Erhalte Dateiendung in Dialog
                        if self.dialog_target_item:
                            t_trunc = truncate_name(self.dialog_target_item.name, self.dialog_target_item.is_dir, avail_name)
                        else:
                            t_trunc = truncate_name(file_name, False, avail_name)
                        left_str = f" „{t_trunc}“ ersetzen?"
                        avail_right = max(0, term_cols - str_width(left_str) - 1)
                        if chosen_opts:
                            hints = " ".join(chosen_opts)
                            st_line = pad_to_width(f"{left_str} {hints}", term_cols)
                        else:
                            st_line = pad_to_width(left_str, term_cols)
                    else:
                        st_line = " " * term_cols
                elif self.active_dialog == "replace_confirm":
                    pr = self.pending_replace or {}
                    pr_name = pr.get("name", "")
                    opts_full = ["[y] Ja", "[n] Nein"]
                    opts_short = ["[y/n]"]
                    opts_mini = ["[y/n]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= term_cols - 2:
                        chosen_opts = opts_full
                    elif sum(str_width(x) for x in opts_short) + 1 <= term_cols - 2:
                        chosen_opts = opts_short
                    else:
                        chosen_opts = opts_mini
                    opts_w = sum(str_width(x) for x in chosen_opts) + max(0, len(chosen_opts) - 1) if chosen_opts else 0
                    avail_name = max(1, term_cols - 12 - opts_w)
                    # Erhalte Dateiendung in Dialog
                    t_trunc = truncate_name(pr_name, pr.get("is_dir_target", False), avail_name)
                    left_str = f" „{t_trunc}“ ersetzen?"
                    if chosen_opts:
                        hints = " ".join(chosen_opts)
                        st_line = pad_to_width(f"{left_str} {hints}", term_cols)
                    else:
                        st_line = pad_to_width(left_str, term_cols)
                elif self.active_dialog == "schnellstart":
                    left_str = " Schnellstart: Eintrag wählen"
                    avail_r = max(1, term_cols - str_width(left_str) - 1)
                    _esc_d = key_display(self.keymap, 'cancel', 'ESC')
                    opts_full = ["[↑↓] Navigieren", "[Eingabe] Starten", f"[{_esc_d}] Zurück"]
                    opts_short = ["[↑↓] Nav", "[Ent] Start", f"[{_esc_d}]"]
                    opts_mini = [f"[{_esc_d}]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= avail_r:
                        hints = distribute_options(opts_full, avail_r)
                    elif str_width(" ".join(opts_short)) <= avail_r:
                        hints = distribute_options(opts_short, avail_r)
                    else:
                        hints = distribute_options(opts_mini, avail_r)
                    st_line = pad_to_width(f"{left_str} {hints}" if hints else left_str, term_cols)
                elif self.active_dialog == "goto_menu":
                    left_str = " Menü: Taste wählen"
                    avail_r = max(1, term_cols - str_width(left_str) - 1)
                    _esc = key_display(self.keymap, "cancel", "ESC")
                    _q = key_display(self.keymap, "quit", "q")
                    opts_full = [f"[{_esc} / {_q}] Zurück"]
                    opts_short = [f"[{_esc} / {_q}] Zurück"]
                    opts_mini = [f"[{_esc}]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= avail_r:
                        hints = distribute_options(opts_full, avail_r)
                    elif str_width(opts_short[0]) <= avail_r:
                        hints = distribute_options(opts_short, avail_r)
                    elif str_width(opts_mini[0]) <= avail_r:
                        hints = distribute_options(opts_mini, avail_r)
                    else:
                        hints = ""
                    st_line = pad_to_width(f"{left_str} {hints}" if hints else left_str, term_cols)
                elif self.active_dialog == "help_menu":
                    left_str = " Hilfe: ↑↓ Scrollen"
                    avail_r = max(1, term_cols - str_width(left_str) - 1)
                    _esc = key_display(self.keymap, "cancel", "ESC")
                    _q = key_display(self.keymap, "quit", "q")
                    opts_full = [f"[{_esc} / {_q}] Zurück"]
                    opts_short = [f"[{_esc} / {_q}] Zurück"]
                    opts_mini = [f"[{_esc}]"]
                    if sum(str_width(x) for x in opts_full) + 2 <= avail_r:
                        hints = distribute_options(opts_full, avail_r)
                    elif str_width(opts_short[0]) <= avail_r:
                        hints = distribute_options(opts_short, avail_r)
                    elif str_width(opts_mini[0]) <= avail_r:
                        hints = distribute_options(opts_mini, avail_r)
                    else:
                        hints = ""
                    st_line = pad_to_width(f"{left_str} {hints}" if hints else left_str, term_cols)
                else:
                    st_line = " " * term_cols
            else:
                if self.show_console and self.console_focused:
                    mode_lbl = "Konsole"
                    left_b = f" {mode_lbl}  " if mode_lbl else " "
                    avail_ctrl = max(1, term_cols - str_width(left_b) - 1)

                    # Dynamische Optionen für die Hilfeleiste in der Konsole;
                    # Tasten aus der keymap (Single Source of Truth)
                    kd = lambda a, d: key_display(self.keymap, a, d)
                    esc_lbl = kd("cancel", "ESC")
                    tab_lbl = kd("console_focus", "Tab")
                    opt_full = [f"[Bild↑/Bild↓] Scrollen", f"[{tab_lbl}] Fokus", f"[{esc_lbl}] Schließen"]
                    opt_short = [f"[Bild↑/↓] Scrollen", f"[{tab_lbl}] Fokus", f"[{esc_lbl}] Schließen"]
                    opt_mini = ["[Bild↑/↓]", f"[{tab_lbl}]", f"[{esc_lbl}]"]
                    opt_esc_only = [f"[{esc_lbl}] Schließen"]
                    opt_esc_mini = [f"[{esc_lbl}]"]

                    w_full = sum(str_width(it) for it in opt_full)
                    w_short = sum(str_width(it) for it in opt_short)
                    w_mini = sum(str_width(it) for it in opt_mini)

                    if w_full + 2 <= avail_ctrl:
                        ctrl = distribute_options(opt_full, avail_ctrl)
                    elif w_short + 2 <= avail_ctrl:
                        ctrl = distribute_options(opt_short, avail_ctrl)
                    elif w_mini + 1 <= avail_ctrl:
                        ctrl = distribute_options(opt_mini, avail_ctrl)
                    elif str_width(opt_esc_only[0]) <= avail_ctrl:
                        ctrl = distribute_options(opt_esc_only, avail_ctrl)
                    elif str_width(opt_esc_mini[0]) <= avail_ctrl:
                        ctrl = distribute_options(opt_esc_mini, avail_ctrl)
                    else:
                        ctrl = ""
                    st_line = pad_to_width(f"{left_b}{ctrl}" if ctrl else left_b, term_cols)
                else:
                    if self.selected_paths:
                        c = len(self.selected_paths)
                        mode_lbl = f"Auswahl: {c}"
                    elif self.clipboard_mode == "cut":
                        c = len(self.clipboard_paths)
                        mode_lbl = f"Ausschneiden: {c}"
                    elif self.clipboard_mode == "copy":
                        c = len(self.clipboard_paths)
                        mode_lbl = f"Kopieren: {c}"
                    else:
                        mode_lbl = ""

                    left_b = f" {mode_lbl}  " if mode_lbl else " "
                    avail_ctrl = max(1, term_cols - str_width(left_b) - (1 if mode_lbl else 2))
                    ctrl = self.build_dynamic_controls(avail_ctrl)
                    st_line = pad_to_width(f"{left_b}{ctrl}", term_cols)

            all_lines.append(st_line)

        # Modale Vordergrund-Menüs im Yazi-Stil zentriert überlagern
        if self.active_dialog == "schnellstart":
            ss_liste = self._schnellstart_liste()
            ss_key = next((k for k, a in self.keymap.items() if a == "schnellstart"), "i")
            ss_items = []
            for si, se in enumerate(ss_liste):
                marker = "▸ " if si == self._ss_auswahl else "  "
                ss_items.append(f"{marker}{si + 1}. {se.get('titel', '')}")
            if self._ss_tiefe:
                parent = self._schnellstart_eintraege()
                for idx in self._ss_tiefe[:-1]:
                    parent = parent[idx].get("untermenu", [])
                titel = f"{parent[self._ss_tiefe[-1]].get('titel', '')} [{ss_key}]"
            else:
                titel = f"Schnellstart [{ss_key}]"
            ss_w = min(term_cols - 4, 44)
            if ss_w >= 24 and term_rows >= 8:
                box_lines, box_w = build_modal_box(titel, ss_items, ss_w)
                box_h = len(box_lines)
                start_x = max(0, (term_cols - box_w) // 2)
                min_y = 2 if has_top_border else 1
                max_y = max(min_y, (term_rows - (2 if has_bottom_border else 1)) - box_h)
                start_y = max(min_y, min(max_y, (term_rows - box_h) // 2))
                for b_idx, bl in enumerate(box_lines):
                    r_pos = start_y + b_idx
                    if 0 <= r_pos < len(all_lines):
                        all_lines[r_pos] = replace_ansi_range(all_lines[r_pos], start_x, bl, box_w, term_cols)
        elif self.active_dialog == "goto_menu":
            goto_items = [
                f"[d] Downloads",
                f"[f] Dokumente",
                f"[-] Gemerkter Ordner (Fallback: zuletzt verwendet)",
                f"[h] Benutzerordner (~)",
                f"[t] Papierkorb",
                f"[i] Pfad manuell eingeben",
                f"[p] Pfad aus Zwischenablage",
            ]
            target_w = min(term_cols - 4, 46)
            if target_w >= 24 and term_rows >= 8:
                goto_key = next((k for k, a in self.keymap.items() if a == "goto"), "g")
                box_lines, box_w = build_modal_box(f"Gehe zu [{goto_key}]", goto_items, target_w)
                box_h = len(box_lines)
                start_x = max(0, (term_cols - box_w) // 2)
                min_y = 2 if has_top_border else 1
                max_y = max(min_y, (term_rows - (2 if has_bottom_border else 1)) - box_h)
                start_y = max(min_y, min(max_y, (term_rows - box_h) // 2))
                for b_idx, bl in enumerate(box_lines):
                    r_pos = start_y + b_idx
                    if 0 <= r_pos < len(all_lines):
                        all_lines[r_pos] = replace_ansi_range(all_lines[r_pos], start_x, bl, box_w, term_cols)

        elif self.active_dialog == "help_menu":
            help_items = build_help_items(self.keybindings)
            border_overhead = (1 if has_top_border else 0) + (1 if has_bottom_border else 0) + (1 if has_status_bar else 0) + 1
            max_box_h = max(6, term_rows - border_overhead - 2)
            target_box_w = min(term_cols - 4, 72)

            if len(help_items) + 2 <= max_box_h:
                visible_items = help_items
            else:
                avail_content_h = max_box_h - 2
                max_scroll = max(0, len(help_items) - avail_content_h)
                self.help_scroll_offset = max(0, min(max_scroll, self.help_scroll_offset))
                visible_items = help_items[self.help_scroll_offset : self.help_scroll_offset + avail_content_h]

            if target_box_w >= 28 and term_rows >= 6:
                box_lines, box_w = build_modal_box("Navigationshilfe [h]", visible_items, target_box_w)
                box_h = len(box_lines)
                start_x = max(0, (term_cols - box_w) // 2)
                min_y = 2 if has_top_border else 1
                max_y = max(min_y, (term_rows - (2 if has_bottom_border else 1)) - box_h)
                start_y = max(min_y, min(max_y, (term_rows - box_h) // 2))
                for b_idx, bl in enumerate(box_lines):
                    r_pos = start_y + b_idx
                    if 0 <= r_pos < len(all_lines):
                        # C_RESET am Zeilenanfang: aktives Fett der überlagerten Zeile
                        # darf nicht in das Hilfe-Menü übernommen werden
                        all_lines[r_pos] = replace_ansi_range(all_lines[r_pos], start_x, f"{C_RESET}{bl}", box_w, term_cols)

        return all_lines[:term_rows]

    def build_dynamic_controls(self, avail_w: int) -> str:
        kd = lambda a, d: key_display(self.keymap, a, d)
        h_lbl, t_lbl = kd("help", "h"), kd("console", "t")
        m_lbl, q_lbl = kd("menu", "m"), kd("quit", "q")
        # Stufe 1: Vollständig mit 5 Optionen (Navigieren, Hilfe, Konsole, Menü, Beenden)
        items_full = ["[←↑↓→] Navigieren", f"[{h_lbl}] Hilfe", f"[{t_lbl}] Konsole", f"[{m_lbl}] Menü", f"[{q_lbl}] Beenden"]
        w_full = sum(str_width(it) for it in items_full)
        if w_full + (len(items_full) - 1) * 1 <= avail_w:
            return f"{distribute_options(items_full, avail_w)}"

        # Stufe 2: 3 Optionen (Navigieren, Hilfe, Beenden)
        items_3 = ["[←↑↓→] Navigieren", f"[{h_lbl}] Hilfe", f"[{q_lbl}] Beenden"]
        w_3 = sum(str_width(it) for it in items_3)
        if w_3 + (len(items_3) - 1) * 1 <= avail_w:
            return f"{distribute_options(items_3, avail_w)}"

        # Stufe 3: 2 Optionen (Navigieren, Hilfe)
        items_2 = ["[←↑↓→] Navigieren", f"[{h_lbl}] Hilfe"]
        w_2 = sum(str_width(it) for it in items_2)
        if w_2 + (len(items_2) - 1) * 1 <= avail_w:
            return f"{distribute_options(items_2, avail_w)}"

        # Stufe 4: Bei wenig Platz: "Nav" statt "Navigieren"
        items_short = ["[←↑↓→] Nav", f"[{h_lbl}] Hilfe"]
        w_short = sum(str_width(it) for it in items_short)
        if w_short + (len(items_short) - 1) * 1 <= avail_w:
            return f"{distribute_options(items_short, avail_w)}"

        # Stufe 5: Nur Navigation kurz
        items_nav = ["[←↑↓→] Nav"]
        if str_width(items_nav[0]) <= avail_w:
            return f"{distribute_options(items_nav, avail_w)}"

        # Stufe 6: Nur Pfeilsymbole
        items_arrows = ["[←↑↓→]"]
        if str_width(items_arrows[0]) <= avail_w:
            return f"{distribute_options(items_arrows, avail_w)}"

        return f"Nav"[:max(0, avail_w)]
