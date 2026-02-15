"""
Shared biomechanics logic: coach, database, categories.
Used by Streamlit app (and optionally by Flask main.py for local use).
"""
import json
import os
import re
from collections import deque
import numpy as np

PATH_JSON = os.path.join(os.path.dirname(__file__), 'complete_exercise_biomechanics_database.json')

NAME_PREFIX_MAP = {
    "BB": "Barbell ", "DB": "Dumbbell ", "CB": "Cable ", "BW": "Bodyweight ",
    "LV": "Machine ", "ST": "Strength Training ", "AS": "Assisted ", "Wt": "Weight ",
    "SM": "Smith Machine", "SI": "Stability Index ", "TB": "Trap Bar"
}

def prettify_exercise_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    prefix, core = "", raw_name
    for length in sorted([len(k) for k in NAME_PREFIX_MAP], reverse=True):
        if len(raw_name) >= length and raw_name[:length] in NAME_PREFIX_MAP:
            prefix = NAME_PREFIX_MAP[raw_name[:length]]
            core = raw_name[length:]
            break
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", core)
    name = " ".join(w.lower() for w in words).strip()
    if name:
        name = name[0].upper() + name[1:]
    return (prefix + name).strip()


class BiomechanicsCoach:
    def __init__(self, exercise_key, database):
        self.db = database
        self.ex_info = self.db['exercises'].get(exercise_key)
        self.template = self.db['base_templates'][self.ex_info['uses_template']]
        self.primary_view_name = self.template.get('primary_view', 'side')
        if self.primary_view_name not in self.template['views']:
            self.primary_view_name = next(iter(self.template['views']))
        self.view_cfg = self.template['views'][self.primary_view_name]
        self.primary_joint_name = self.template['primary_joint']
        if self.primary_joint_name not in self.view_cfg:
            for joint, cfg in self.view_cfg.items():
                if cfg.get('type') == 'primary':
                    self.primary_joint_name = joint
                    break
            else:
                self.primary_joint_name = next(iter(self.view_cfg))
        primary_cfg = self.view_cfg[self.primary_joint_name]
        self.flexed_target = primary_cfg.get('flexed') or primary_cfg.get('parallel') or primary_cfg.get('bent')
        self.extended_target = primary_cfg.get('extended') or primary_cfg.get('standing') or primary_cfg.get('lockout')
        self.primary_tolerance = primary_cfg.get('tolerance', 15)
        self.rep_flex_threshold = self.flexed_target + self.primary_tolerance * 0.5
        self.rep_ext_threshold = self.extended_target - self.primary_tolerance * 0.5
        self.min_visibility = 0.6
        self.reps = 0
        self.stage = "extended"
        self.current_angle = 180
        self.feedback = "READY"
        self.form_issue = ""
        self.joint_colors = {}
        self.smoothing_buffer = deque(maxlen=20)
        self.last_bad_form_time = 0
        self.warning_duration = 2.0
        self.last_valid_results = None
        self.last_valid_time = 0.0

    def _calculate_angle(self, a, b, c):
        ba = np.array([a['x'] - b['x'], a['y'] - b['y']])
        bc = np.array([c['x'] - b['x'], c['y'] - b['y']])
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        return np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))

    def process_form(self, lm, current_timestamp):
        primary_left_key = f"left{self.primary_joint_name}"
        primary_right_key = f"right{self.primary_joint_name}"
        if primary_left_key in lm and primary_right_key in lm:
            primary_side = "left" if lm[primary_left_key]['vis'] >= lm[primary_right_key]['vis'] else "right"
        else:
            primary_side = "left" if lm.get('leftelbow', {'vis': 0})['vis'] > lm.get('rightelbow', {'vis': 0})['vis'] else "right"
        frame_is_excellent = True
        self.joint_colors = {}
        current_issues = []
        self.stability_feedback = "Stability: OK"
        primary_grace = 15
        pts_map_template = {
            'elbow': ['shoulder', 'elbow', 'wrist'], 'shoulder': ['hip', 'shoulder', 'elbow'],
            'hip': ['shoulder', 'hip', 'knee'], 'knee': ['hip', 'knee', 'ankle'],
            'ankle': ['knee', 'ankle', 'footindex']
        }
        primary_angles = {"left": 180, "right": 180}
        for side in ("left", "right"):
            for joint_name, cfg in self.view_cfg.items():
                if joint_name not in pts_map_template:
                    continue
                keys = [f"{side}{p}" for p in pts_map_template[joint_name]]
                pts = [lm.get(k, {'x': 0, 'y': 0, 'vis': 0}) for k in keys]
                if any(p['vis'] < self.min_visibility for p in pts):
                    continue
                angle = self._calculate_angle(*pts)
                status = "green"
                if joint_name == self.primary_joint_name:
                    primary_angles[side] = angle
                if cfg.get('type') == "stability":
                    target = cfg.get('target') or cfg.get('upright') or 180
                    max_dev = cfg.get('max_deviation') or 15
                    if abs(angle - target) > max_dev:
                        status = "red"
                        frame_is_excellent = False
                        current_issues.append(f"STABILIZE {joint_name.upper()}")
                        self.stability_feedback = f"{joint_name.title()}: {int(angle)}\u00b0 (Target ~{target}\u00b0)"
                self.joint_colors[f"{side.upper()}_{joint_name.upper()}"] = (0, 255, 0) if status == "green" else (0, 0, 255)
        self.current_angle = primary_angles[primary_side]
        if self.stage == "extended":
            self.feedback = "GO FURTHER" if self.current_angle > self.rep_flex_threshold else "GOOD DEPTH"
        elif self.stage == "flexed":
            self.feedback = "FULL EXTENSION" if self.current_angle < self.rep_ext_threshold else "GOOD EXTENSION"
        form_ok = (current_timestamp - self.last_bad_form_time) >= self.warning_duration
        if not form_ok:
            self.feedback = "FIX FORM"
            self.form_issue = current_issues[0] if current_issues else ""
        else:
            self.form_issue = current_issues[0] if current_issues else ""
        for side in ("left", "right"):
            angle = primary_angles[side]
            pk = f"{side.upper()}_{self.primary_joint_name.upper()}"
            if pk not in self.joint_colors:
                continue
            if not form_ok:
                primary_status = "red"
            else:
                at_full_extension = angle >= (self.rep_ext_threshold - primary_grace)
                at_good_depth = angle <= (self.rep_flex_threshold + primary_grace)
                primary_status = "green" if (at_full_extension or at_good_depth) else "red"
            self.joint_colors[pk] = (0, 255, 0) if primary_status == "green" else (0, 0, 255)
        self.smoothing_buffer.append(frame_is_excellent)
        bad_frame_count = self.smoothing_buffer.count(False)
        if bad_frame_count > (self.smoothing_buffer.maxlen * 0.3):
            self.last_bad_form_time = current_timestamp
            if current_issues:
                self.form_issue = current_issues[0]
        if not form_ok:
            return self.reps
        if self.current_angle <= self.rep_flex_threshold:
            if self.stage == "extended":
                self.stage = "flexed"
        if self.current_angle >= self.rep_ext_threshold:
            if self.stage == "flexed":
                self.reps += 1
                self.stage = "extended"
        return self.reps


def load_db():
    with open(PATH_JSON, 'r') as f:
        return json.load(f)


def is_exercise_valid_for_ui(exercise_key: str, db: dict) -> bool:
    try:
        ex_info = db['exercises'].get(exercise_key)
        if not ex_info or not ex_info.get('uses_template'):
            return False
        template = db['base_templates'].get(ex_info['uses_template'])
        if not template or not template.get('views'):
            return False
        primary_view_name = template.get('primary_view', 'side')
        if primary_view_name not in template['views']:
            primary_view_name = next(iter(template['views']))
        view_cfg = template['views'].get(primary_view_name, {})
        primary_joint_name = template.get('primary_joint')
        if not primary_joint_name or primary_joint_name not in view_cfg:
            for joint, cfg in view_cfg.items():
                if cfg.get('type') == 'primary':
                    primary_joint_name = joint
                    break
            else:
                primary_joint_name = next(iter(view_cfg))
        primary_cfg = view_cfg.get(primary_joint_name, {})
        flexed = primary_cfg.get('flexed') or primary_cfg.get('parallel') or primary_cfg.get('bent')
        extended = primary_cfg.get('extended') or primary_cfg.get('standing') or primary_cfg.get('lockout')
        return flexed is not None and extended is not None
    except Exception:
        return False


def get_categories_list(db: dict):
    categories = set()
    for key, exercise_data in db['exercises'].items():
        if exercise_data.get('uses_template') and is_exercise_valid_for_ui(key, db):
            cat = exercise_data['category']
            categories.add('Legs' if cat in ('Thighs', 'Calves') else cat)
    return sorted(list(categories))


def get_exercises_list(db: dict, category: str):
    allowed_cats = ('Thighs', 'Calves') if category == 'Legs' else (category,)
    out = []
    for key, exercise_data in db['exercises'].items():
        if exercise_data['category'] in allowed_cats and exercise_data.get('uses_template') and is_exercise_valid_for_ui(key, db):
            out.append({'key': key, 'name': prettify_exercise_name(exercise_data['full_name']), 'category': exercise_data['category']})
    return sorted(out, key=lambda x: x['name'])


def get_first_valid_exercise_key(db: dict):
    for key, exercise_data in db['exercises'].items():
        if exercise_data.get('uses_template') and is_exercise_valid_for_ui(key, db):
            return key
    return "BBCurl"
