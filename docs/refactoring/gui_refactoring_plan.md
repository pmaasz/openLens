# GUI Refactoring Plan - Phase 4
## Incremental Integration of Controllers

**Date:** 2026-02-06  
**Status:** In Progress  
**Priority:** Medium (Phase 4)

---

## 📊 Current State Analysis

### Main GUI Class: LensEditorWindow
- **File:** src/lens_editor_gui.py
- **Size:** 2,198 lines
- **Methods:** 53
- **Tabs:** 6 main tabs

### Existing Controllers
- ✅ LensSelectionController (created)
- ✅ LensEditorController (created)
- ✅ SimulationController (created)
- ✅ PerformanceController (created)
- ⚠️ Not yet integrated into main GUI

---

## 🎯 Refactoring Strategy

### Approach: **Incremental Integration**
- One tab at a time
- Test after each integration
- Maintain backward compatibility
- No breaking changes

### Priority Order:
1. **Selection Tab** (simplest, foundation)
2. **Editor Tab** (most used)
3. **Simulation Tab** (ray tracing)
4. **Performance Tab** (aberrations)
5. **Comparison Tab** (lower priority)
6. **Export Tab** (lower priority)

---

## 📋 Phase 4.1: Selection Tab Integration (2 hours)

### Current Implementation
**File:** lens_editor_gui.py  
**Lines:** ~400-600  
**Methods:**
- `setup_selection_tab()` - ~150 lines
- `refresh_lens_list()` - ~20 lines
- `on_lens_selected()` - ~30 lines
- `create_new_lens()` - ~40 lines
- `delete_lens()` - ~30 lines
- `duplicate_lens()` - ~25 lines

### Integration Steps

#### Step 1: Import Controller
#### Step 2: Initialize Controller
#### Step 3: Delegate Tab Setup
#### Step 4: Update Method Calls
#### Step 5: Test Integration
#### Step 6: Clean Up Old Code
#### Step 7: Commit

### Success Criteria
- ✅ Selection tab works identically
- ✅ All tests pass
- ✅ ~150 lines removed from main GUI
- ✅ Controller properly integrated

---

## 📊 Expected Results

### Final Target (After All Phases)
```
lens_editor_gui.py:
  Lines: ~1,500 (-698, -32%)
  Methods: ~35 (-18, -34%)
  Reduction: 32% ✅
```

---

## 📅 Timeline

- Phase 4.1: Selection Tab (2 hours) ⭐
- Phase 4.2: Editor Tab (2 hours) ⭐⭐
- Phase 4.3: Simulation Tab (2 hours) ⭐⭐
- Phase 4.4: Performance Tab (2 hours) ⭐

**Total Time: 8 hours**

---

**Status:** Starting Phase 4.1  
**Next Action:** Begin Selection tab integration
