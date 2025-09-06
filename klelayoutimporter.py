import pcbnew
import wx
import json
import re

class KLELayoutImporterPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "KLE Layout Importer"
        self.category = "Placement"
        self.description = "Automatically places switches based on a JSON layout file"
        self.show_toolbar_button = True
        self.icon_file_name = "icon.png"

        self.key_pitch = 19.05 #mm
        self.x_d_offset = 0.45 # offset of diodes, unit of key_pitch
        self.y_d_offset = -0.245 # unit of key_pitch
        self.d_angle = 90 # degree

    def Run(self):
        # ファイル選択ダイアログ
        dialog = wx.FileDialog(
            None, "Choose layout JSON file", "", "",
            "JSON files (*.json)|*.json", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dialog.ShowModal() == wx.ID_CANCEL:
            return  # キャンセルされた場合は何もしない

        path = dialog.GetPath()
        dialog.Destroy()

        # JSON読み込み
        with open(path, "r", encoding="utf-8") as f:
            json_layout = json.load(f)

        key_positions = self.parse_layout(json_layout)

    def parse_layout(self, json_layout):
        layout = []
        current_y = 0

        for row in json_layout:
            current_x = 0
            default_w = 1
            default_h = 1
            w = default_w
            h = default_h

            # skip header block
            is_header = False
            for item in row:
                if 'author' in item:
                    is_header = True
                if 'name' in item:
                    is_header = True
                
            if is_header:
                continue

            # debug
            #wx.MessageBox(f"{row}", "message", wx.OK)
            
            for item in row:
                if isinstance(item, dict):
                    if 'x' in item:
                        current_x += item['x']
                    if 'y' in item:
                        current_y += item['y']
                    if 'w' in item:
                        w = item['w']
                    if 'h' in item:
                        h = item['h']
                elif isinstance(item, str):
                    layout.append({
                        'label': item,
                        'x': current_x,
                        'y': current_y,
                        'w': w,
                        'h': h
                    })
                    self.place_footprint({
                        'label': item,
                        'x': current_x,
                        'y': current_y,
                        'w': w,
                        'h': h },
                                         current_x,
                                         current_y,
                                         w
                    )
                    current_x += w
                    # 次のキーのためにリセット
                    w = default_w
                    h = default_h
            current_y += 1
        return layout

    def is_sw_number(self, s):
        pattern = r"^SW\d+$"
        return bool(re.match(pattern,s))

    def is_diode_number(self, s):
        pattern = r"^D\d+$"
        return bool(re.match(pattern,s))

    def is_number_same(self, s1, s2, prefix1='SW', prefix2='D'):
        if s1.startswith(prefix1) and s2.startswith(prefix2):
            num1 = s1[len(prefix1):]
            num2 = s2[len(prefix2):]
            return num1 == num2
        return False

    def place_footprint(self, key, x_sw_u, y_sw_u, w_u):
        board = pcbnew.GetBoard()
        footprints = list(board.GetFootprints())

        switch_fps = [fp for fp in footprints if self.is_sw_number(fp.GetReference())]
        diode_fps = [fp for fp in footprints if self.is_diode_number(fp.GetReference())]

        unit = pcbnew.FromMM(self.key_pitch)


        matched_fp = next(
            (fp for fp in switch_fps if fp.GetValue().strip().lower() == key['label'].strip().lower()),
            None
        )
        if not matched_fp:
            wx.MessageBox(f"Not found FP: {key['label']}", "Warning", wx.OK)
            return

        x_sw = (x_sw_u + 0.5*w_u)* unit
        y_sw = (y_sw_u + 0.5)* unit
        matched_fp.SetPosition(pcbnew.VECTOR2I(int(x_sw), int(y_sw)))

        matched_d = next(
            (diode for diode in diode_fps if self.is_number_same(matched_fp.GetReference(),diode.GetReference())),
            None
        )
        if not matched_d:
            wx.MessageBox(f"Not found Diode for: {matched_fp.GetValue().strip()}", "Warning", wx.OK)

        x_d = (self.x_d_offset) * unit + x_sw
        y_d = (self.y_d_offset) * unit + y_sw
        if not matched_d.IsFlipped():
            matched_d.Flip(board.GetDesignSettings().GetAuxOrigin(), True)
        matched_d.SetPosition(pcbnew.VECTOR2I(int(x_d), int(y_d)))
        matched_d.SetOrientationDegrees(self.d_angle)
            
        pcbnew.Refresh()

