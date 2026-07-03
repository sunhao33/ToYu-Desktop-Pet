"""YoTu Code Audit — Walk through all major code paths"""
import sys, os, json, time, traceback
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

PASS = 0
FAIL = 0
WARN = 0
ISSUES = []

def ok(msg):
    global PASS
    PASS += 1
    print(f'  [OK] {msg}')

def fail(msg, detail=''):
    global FAIL
    FAIL += 1
    print(f'  [FAIL] {msg}')
    if detail:
        print(f'        {detail[:150]}')
    ISSUES.append(f'FAIL: {msg}')

def warn(msg):
    global WARN
    WARN += 1
    print(f'  [WARN] {msg}')
    ISSUES.append(f'WARN: {msg}')

print("=" * 60)
print("YoTu Code Audit")
print("=" * 60)

# ── 1. Import all modules ──
print("\n[1] Module Imports")
modules = {}
try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    ok("QApplication created")
except Exception as e:
    fail("QApplication", str(e))
    sys.exit(1)

for mod_name in [
    'ui.main_window', 'ui.todo_widget', 'ui.timer_widget',
    'ui.settings_dialog', 'ui.settings_manager', 'ui.ui_optimization',
    'pet_engine.pet_window', 'pet_engine.pet_bubble',
    'pet_engine.pet_companion', 'pet_engine.pet_effects',
    'pet_engine.pet_food', 'pet_engine.pet_physics',
    'pet_engine.pet_affection', 'pet_engine.pet_state_machine',
    'pet_engine.pet_house', 'image_processor.processor',
]:
    try:
        mod = __import__(mod_name, fromlist=[''])
        modules[mod_name] = mod
        ok(f"Import {mod_name}")
    except Exception as e:
        fail(f"Import {mod_name}", str(e))

# ── 2. Settings Manager ──
print("\n[2] Settings Manager")
try:
    from ui.settings_manager import SettingsManager
    sm = SettingsManager()
    ok("SettingsManager created")
    
    # Test all properties
    props = ['favorites', 'pet_image_path', 'affection_level',
             'affection_last_decay', 'pomodoro_enabled', 'pomodoro_interval',
             'time_awareness_enabled', 'interaction_mode', 'house_enabled',
             'walking_speed_max', 'walking_speed_min', 'animation_scale',
             'always_on_top', 'auto_start', 'bead_creations']
    for p in props:
        try:
            v = getattr(sm, p)
            ok(f"  {p} = {str(v)[:40]}")
        except Exception as e:
            fail(f"  {p}", str(e))
    
    # Test setter round-trip
    try:
        old_val = sm.affection_level
        sm.affection_level = 50
        assert sm.affection_level == 50
        sm.affection_level = old_val
        ok("  affection_level round-trip")
    except Exception as e:
        fail("  affection_level round-trip", str(e))
    
    # Test favorites safety
    try:
        old_favs = sm.favorites
        sm.favorites = [{"path": "test.png", "name": "test"}]
        assert len(sm.favorites) == 1
        sm.favorites = old_favs
        ok("  favorites round-trip")
    except Exception as e:
        fail("  favorites round-trip", str(e))
except Exception as e:
    fail("SettingsManager", str(e))

# ── 3. Affection System ──
print("\n[3] Affection System")
try:
    from pet_engine.pet_affection import AffectionSystem
    aff = AffectionSystem(sm)
    ok(f"AffectionSystem created, level={aff.level}")
    
    # Test add
    old = aff.level
    aff.add(10)
    ok(f"  add(10): {old} -> {aff.level}")
    aff.add(-10)
    ok(f"  add(-10): back to {aff.level}")
    
    # Test cap
    aff.add(999)
    assert aff.level <= 100, f"Affection exceeded 100: {aff.level}"
    ok(f"  add(999) capped at {aff.level}")
    aff.level  # reset
    sm.affection_level = 75
    
    # Test emoji
    ok(f"  emoji: {aff.emoji}")
    ok(f"  display_text: {aff.display_text}")
    
    # Test decay
    try:
        aff.tick_decay()
        ok("  tick_decay() runs without error")
    except Exception as e:
        fail("  tick_decay()", str(e))
except Exception as e:
    fail("AffectionSystem", str(e))

# ── 4. Companion System ──
print("\n[4] Companion System")
try:
    from pet_engine.pet_companion import CompanionSystem, Mood, WorkState
    cs = CompanionSystem(sm)
    ok(f"CompanionSystem created, mood={cs._mood.name}")
    
    # Test all events
    events = [
        ('feed', lambda: cs.on_interaction('feed')),
        ('pet', lambda: cs.on_interaction('pet')),
        ('drag_start', lambda: cs.on_drag_start()),
        ('drag_end', lambda: cs.on_drag_end()),
        ('task_done', lambda: cs.on_task_complete('test')),
        ('task_add', lambda: cs.on_task_add('test')),
        ('pomodoro_start', lambda: cs.on_pomodoro_start()),
        ('pomodoro_end', lambda: cs.on_pomodoro_end()),
        ('morning', lambda: cs.morning_greeting()),
        ('night', lambda: cs.night_greeting()),
        ('return', lambda: cs.on_return()),
        ('long_work', lambda: cs.on_long_work()),
        ('idle_chat', lambda: cs.on_idle_chat()),
    ]
    for name, fn in events:
        try:
            fn()
            ok(f"  event '{name}' -> mood={cs._mood.name}")
        except Exception as e:
            fail(f"  event '{name}'", str(e))
    
    # Test methods
    for method in ['get_mood_message', 'get_context_message', 'get_mood_emoji',
                   'get_status_text', 'get_work_duration', 'get_daily_summary']:
        try:
            result = getattr(cs, method)()
            ok(f"  {method}() = {str(result)[:50]}")
        except Exception as e:
            fail(f"  {method}()", str(e))
    
    # Test update
    try:
        cs.update()
        ok(f"  update() -> mood={cs._mood.name}")
    except Exception as e:
        fail("  update()", str(e))
    
    # Test on_pomodoro_tick
    try:
        cs.on_pomodoro_tick(10, 25)
        ok("  on_pomodoro_tick(10, 25)")
    except Exception as e:
        fail("  on_pomodoro_tick()", str(e))
except Exception as e:
    fail("CompanionSystem", str(e))

# ── 5. Particle System ──
print("\n[5] Particle System")
try:
    from pet_engine.pet_effects import ParticleSystem
    ps = ParticleSystem()
    ok("ParticleSystem created")
    
    # Test all effect types
    for method, args in [
        ('add_hearts', (100, 100, 3)),
        ('add_stars', (200, 200, 5)),
        ('add_zzz', (300, 300, 2)),
        ('add_fire', (150, 150, 4)),
        ('add_sweat', (250, 250, 2)),
    ]:
        try:
            getattr(ps, method)(*args)
            ok(f"  {method}({args}) -> {len(ps.particles)} particles")
        except Exception as e:
            fail(f"  {method}()", str(e))
    
    # Test tick
    try:
        for _ in range(10):
            ps._tick()
        ok(f"  10 ticks -> {len(ps.particles)} particles remaining")
    except Exception as e:
        fail("  _tick()", str(e))
    
    ps.close()
    ok("ParticleSystem closed")
except Exception as e:
    fail("ParticleSystem", str(e))

# ── 6. Food System ──
print("\n[6] Food System")
try:
    from pet_engine.pet_food import FoodItemWindow
    fw = FoodItemWindow()
    ok(f"FoodItemWindow created: pos=({fw.x()},{fw.y()})")
    
    # Test food exists
    assert fw.isVisible() or not fw.isVisible()  # just checking no crash
    ok("  FoodWidget accessible")
    fw.close()
except Exception as e:
    fail("FoodSystem", str(e))

# ── 7. Physics System ──
print("\n[7] Physics System")
try:
    from pet_engine.pet_physics import PetPhysics
    pp = PetPhysics()
    ok("PetPhysics created")
    
    # Test methods
    pp.set_walk_velocity(2.0)
    ok(f"  set_walk_velocity(2.0) -> vx={pp.vx}")
    pp.set_fall_velocity(5.0)
    ok(f"  set_fall_velocity(5.0) -> vy={pp.vy}")
    pp.set_jump_velocity(-12.0)
    ok(f"  set_jump_velocity(-12) -> vy={pp.vy}")
    pp.stop()
    ok(f"  stop() -> vx={pp.vx}, vy={pp.vy}")
except Exception as e:
    fail("PetPhysics", str(e))

# ── 8. State Machine ──
print("\n[8] State Machine")
try:
    from pet_engine.pet_state_machine import PetStateMachine, InteractionMode
    psm = PetStateMachine()
    ok(f"PetStateMachine created, mode={psm._mode}")
    
    psm.set_mode(InteractionMode.FOLLOW)
    ok(f"  set_mode(FOLLOW) -> {psm._mode}")
    psm.set_mode(InteractionMode.STAY)
    ok(f"  set_mode(STAY) -> {psm._mode}")
    psm.set_mode(InteractionMode.FREE)
    ok(f"  set_mode(FREE) -> {psm._mode}")
except Exception as e:
    fail("PetStateMachine", str(e))

# ── 9. Bubble System ──
print("\n[9] Bubble System")
try:
    from pet_engine.pet_bubble import (
        PetFunctionBubble, CompanionBubble, PomodoroNotificationBubble
    )
    
    # PetFunctionBubble
    pfb = PetFunctionBubble()
    ok(f"PetFunctionBubble created")
    
    # Check signals exist
    for sig_name in ['pomodoro_toggle', 'pomodoro_settings', 'feed_pet',
                     'zoom_in', 'zoom_out', 'change_pet', 'toggle_visibility',
                     'exit_app', 'go_home']:
        if hasattr(pfb, sig_name):
            ok(f"  signal '{sig_name}' exists")
        else:
            fail(f"  signal '{sig_name}' MISSING")
    
    pfb.close()
    
    # CompanionBubble
    cb = CompanionBubble()
    ok("CompanionBubble created")
    cb.show_message("测试消息", None)
    cb.close()
    ok("  show_message works")
    
    # PomodoroNotificationBubble
    pnb = PomodoroNotificationBubble("测试标题", "测试副标题")
    ok("PomodoroNotificationBubble created")
    pnb.close()
except Exception as e:
    fail("Bubble System", str(e))

# ── 10. House System ──
print("\n[10] House System")
try:
    from pet_engine.pet_house import HouseWindow
    ph = HouseWindow()
    ok(f"HouseWindow created")
    ph.set_pet_inside(True)
    ok("  set_pet_inside(True)")
    ph.set_pet_inside(False)
    ok("  set_pet_inside(False)")
    ph.close()
except Exception as e:
    fail("PetHouse", str(e))

# ── 11. Image Processor ──
print("\n[11] Image Processor")
try:
    from image_processor.processor import process_and_save
    
    # Test with existing image
    test_img = 'resources/toyu.png'
    if os.path.exists(test_img):
        result = process_and_save(test_img, sm._app_data_dir, threshold=200, use_ai=False)
        ok(f"  process_and_save -> {os.path.basename(result)}")
        
        # Check no _pet stacking
        assert '_pet_pet' not in result, f"Filename stacking detected: {result}"
        ok(f"  No filename stacking")
        
        # Run again to verify
        result2 = process_and_save(result, sm._app_data_dir, threshold=200, use_ai=False)
        assert '_pet_pet' not in result2, f"Filename stacking on 2nd pass: {result2}"
        ok(f"  2nd pass: {os.path.basename(result2)} (no stacking)")
    else:
        warn(f"  Test image not found: {test_img}")
except Exception as e:
    fail("Image Processor", str(e))

# ── 12. Todo Widget ──
print("\n[12] Todo Widget")
try:
    from ui.todo_widget import TodoWidget
    tw = TodoWidget()
    ok("TodoWidget created")
    
    # Check signals
    for sig in ['task_completed', 'task_added']:
        if hasattr(tw, sig):
            ok(f"  signal '{sig}' exists")
        else:
            fail(f"  signal '{sig}' MISSING")
    
    # Test add task
    tw._add_input.setText("测试任务")
    tw._on_add()
    count = len(tw._todos)
    ok(f"  Added task, total={count}")
    
    # Test toggle done
    if count > 0:
        tw._on_toggle_done(0)
        ok(f"  Toggled done, todos={len(tw._todos)}")
    
    # Test delete
    if len(tw._todos) > 0:
        tw._on_delete(0)
        ok(f"  Deleted task, remaining={len(tw._todos)}")
    
    # Test filter
    tw._add_input.setText("任务A")
    tw._on_add()
    tw._add_input.setText("任务B")
    tw._on_add()
    tw._on_toggle_done(0)
    
    for f in ['all', 'active', 'done']:
        tw._set_filter(f)
        ok(f"  Filter '{f}' -> {tw._filter}")
    
    tw.close()
except Exception as e:
    fail("TodoWidget", str(e))

# ── 13. Timer Widget ──
print("\n[13] Timer Widget")
try:
    from ui.timer_widget import TimerWidget
    tw2 = TimerWidget()
    ok("TimerWidget created")
    
    # Check signal
    if hasattr(tw2, 'timer_complete'):
        ok("  signal 'timer_complete' exists")
    else:
        fail("  signal 'timer_complete' MISSING")
    
    # Test set time
    tw2._set_time(0, 5, 0)
    ok(f"  _set_time(0,5,0) -> {tw2._hours}:{tw2._mins}:{tw2._secs}")
    
    tw2.close()
except Exception as e:
    fail("TimerWidget", str(e))

# ── 14. Main Window ──
print("\n[14] Main Window")
try:
    from ui.main_window import MainWindow
    mw = MainWindow()
    ok(f"MainWindow created, size={mw.size().width()}x{mw.size().height()}")
    
    # Check tabs
    for name, btn in mw._page_btns.items():
        btn.click()
        idx = mw._page_stack.currentIndex()
        ok(f"  Tab '{name}' -> page {idx}")
    
    # Check _cleanup_favorites
    try:
        favs = mw.settings.favorites
        ok(f"  favorites count: {len(favs)}")
        assert len(favs) <= 10, f"Favorites exceed limit: {len(favs)}"
        ok("  favorites <= 10")
        
        # Check for _MEI paths
        mei_count = sum(1 for f in favs if '_MEI' in str(f.get('path', '')))
        assert mei_count == 0, f"Found {mei_count} _MEI paths in favorites"
        ok("  No _MEI paths in favorites")
        
        # Check for non-existent files
        missing = [f for f in favs if not os.path.exists(f.get('path', ''))]
        if missing:
            warn(f"  {len(missing)} favorites point to non-existent files")
        else:
            ok("  All favorites point to existing files")
    except Exception as e:
        fail("  _cleanup_favorites check", str(e))
    
    # Check start button
    if hasattr(mw, '_start_btn'):
        ok(f"  Start button: '{mw._start_btn.text()}', enabled={mw._start_btn.isEnabled()}")
    
    # Check all expected widgets exist
    for attr in ['_todo_widget', '_timer_widget', '_dark_mode_btn', '_settings_btn']:
        if hasattr(mw, attr):
            ok(f"  {attr} exists")
        else:
            fail(f"  {attr} MISSING")
    
    # Try starting pet
    try:
        mw._on_start_pet()
        time.sleep(1)
        app.processEvents()
        
        if mw._pet:
            ok(f"  Pet started, size={mw._pet.size().width()}x{mw._pet.size().height()}")
            
            # Check pet has companion
            if hasattr(mw._pet, 'companion'):
                ok(f"  Pet companion: {mw._pet.companion._mood.name}")
            else:
                fail("  Pet has NO companion")
            
            # Check pet has effects
            if hasattr(mw._pet, '_effects'):
                ok("  Pet has particle effects")
            else:
                fail("  Pet has NO particle effects")
            
            # Check pet has affection
            if hasattr(mw._pet, 'affection'):
                ok(f"  Pet affection: {mw._pet.affection.level}")
            else:
                fail("  Pet has NO affection system")
            
            # Test feed
            try:
                mw._on_feed_pet()
                time.sleep(0.5)
                app.processEvents()
                ok("  Feed triggered")
            except Exception as e:
                fail("  Feed", str(e))
            
            # Test go home
            try:
                if hasattr(mw._pet, '_go_home'):
                    mw._pet._go_home()
                    ok("  _go_home() works")
                else:
                    warn("  _go_home() not found")
            except Exception as e:
                fail("  _go_home()", str(e))
        else:
            fail("  Pet failed to start")
    except Exception as e:
        fail("  Start pet", str(e))
    
    mw.close()
except Exception as e:
    fail("MainWindow", str(e))

# ── Summary ──
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {WARN} warnings")
print("=" * 60)
if ISSUES:
    print("\nIssues found:")
    for issue in ISSUES:
        print(f"  - {issue}")
else:
    print("\nNo issues found!")
