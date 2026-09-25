/* Shared client-side plumbing for any page that edits an instance's JSON
 * config through [data-path] form fields - the Config page's own sections,
 * and any plugin's "config_form" page section (see mbiiez/web/formify.py:
 * describe_field_spec and plugin_loader.call_web_config_sections /
 * call_web_page). Kept as one file so a fix or a new widget kind (see
 * form-field.html) only has to be made once. */
window.MbiiezConfigForm = (function () {
  'use strict';

  function setPath(obj, dottedPath, value) {
    const parts = dottedPath.split('.');
    let cur = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i];
      if (typeof cur[p] !== 'object' || cur[p] === null) cur[p] = {};
      cur = cur[p];
    }
    cur[parts[parts.length - 1]] = value;
  }

  // Chip-list widgets: the reorderable map rotation, holiday map pools,
  // and any plugin's "map_list"/plain list fields. `data-reorderable`
  // (set by formify.py, not guessed from the field's path) decides
  // whether up/down controls are shown.
  function initChipWidgets(root) {
    const chipState = {};

    function renderChips(widget) {
      const path = widget.dataset.chipPath;
      const container = widget.querySelector('.chip-container');
      container.innerHTML = '';
      const values = chipState[path];
      const reorderable = widget.dataset.reorderable === 'true';

      values.forEach(function (val, idx) {
        const chip = document.createElement('span');
        chip.className = 'badge text-bg-secondary d-inline-flex align-items-center gap-1 p-2';
        const label = document.createElement('span');
        label.textContent = val;
        chip.appendChild(label);

        if (reorderable) {
          const up = document.createElement('button');
          up.type = 'button';
          up.className = 'btn btn-sm btn-link p-0 text-white';
          up.title = 'Move up';
          up.innerHTML = '<i class="fas fa-arrow-up"></i>';
          up.onclick = function () {
            if (idx > 0) {
              const tmp = values[idx - 1];
              values[idx - 1] = values[idx];
              values[idx] = tmp;
              renderChips(widget);
            }
          };
          chip.appendChild(up);

          const down = document.createElement('button');
          down.type = 'button';
          down.className = 'btn btn-sm btn-link p-0 text-white';
          down.title = 'Move down';
          down.innerHTML = '<i class="fas fa-arrow-down"></i>';
          down.onclick = function () {
            if (idx < values.length - 1) {
              const tmp = values[idx + 1];
              values[idx + 1] = values[idx];
              values[idx] = tmp;
              renderChips(widget);
            }
          };
          chip.appendChild(down);
        }

        const rm = document.createElement('button');
        rm.type = 'button';
        rm.className = 'btn-close btn-close-white';
        rm.style.fontSize = '0.6rem';
        rm.title = 'Remove';
        rm.onclick = function () {
          values.splice(idx, 1);
          renderChips(widget);
        };
        chip.appendChild(rm);

        container.appendChild(chip);
      });
    }

    root.querySelectorAll('.chip-list-widget').forEach(function (widget) {
      const path = widget.dataset.chipPath;
      const initialScript = widget.parentElement.querySelector('.chip-initial-values');
      chipState[path] = JSON.parse(initialScript.textContent);
      renderChips(widget);

      const addInput = widget.querySelector('.chip-add-input');
      const addBtn = widget.querySelector('.chip-add-btn');
      function doAdd() {
        const val = addInput.value.trim();
        if (!val) return;
        chipState[path].push(val);
        addInput.value = '';
        renderChips(widget);
      }
      addBtn.addEventListener('click', doAdd);
      addInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          doAdd();
        }
      });
    });

    return { chipState: chipState, renderChips: renderChips };
  }

  // A field wrapper with data-depends-on='{"path": "...", "equals": 1}'
  // gets disabled + dimmed whenever the named other field (found by its
  // own data-path) isn't currently equal to that value - e.g. RTV's rate/
  // timing fields depending on RTV itself being enabled.
  function initDependsOn(root) {
    root.querySelectorAll('[data-depends-on]').forEach(function (wrapper) {
      let rule;
      try {
        rule = JSON.parse(wrapper.dataset.dependsOn);
      } catch (e) {
        return;
      }
      const controller = root.querySelector('[data-path="' + rule.path + '"]');
      if (!controller) return;

      function apply() {
        const val = controller.type === 'checkbox' ? (controller.checked ? 1 : 0) : controller.value;
        const active = ('not_equals' in rule)
          ? String(val) !== String(rule.not_equals)
          : String(val) === String(rule.equals);
        wrapper.querySelectorAll('input, select, textarea, button').forEach(function (el) {
          el.disabled = !active;
        });
        wrapper.style.opacity = active ? '' : '0.55';
      }
      controller.addEventListener('input', apply);
      controller.addEventListener('change', apply);
      apply();
    });
  }

  // Composite fields (formify "composite"): several labelled inputs for
  // one space-separated value like "1 5". Rebuilds the hidden [data-path]
  // input on every change - hiding parts whose data-show-when rule isn't
  // met and leaving them out of the value - and fires 'change' on it so
  // anything depending on it re-evaluates. A visible number part left
  // empty is flagged .is-invalid, which buildConfig refuses to save.
  function initCompositeFields(root) {
    root.querySelectorAll('.composite-field').forEach(function (field) {
      const hidden = field.querySelector('input[type="hidden"][data-path]');
      const wraps = Array.prototype.slice.call(field.querySelectorAll('.composite-part-wrap'));
      const inputs = wraps.map(function (w) { return w.querySelector('.composite-part'); });
      const preview = field.querySelector('.composite-preview');

      function rebuild(initial) {
        const tokens = [];
        wraps.forEach(function (wrap, i) {
          let visible = true;
          if (wrap.dataset.showWhen) {
            try {
              const rule = JSON.parse(wrap.dataset.showWhen);
              const other = inputs[rule.part];
              visible = rule.in.map(String).indexOf(String(other.value)) !== -1;
            } catch (e) { /* malformed rule - just show the part */ }
          }
          wrap.style.display = visible ? '' : 'none';
          const input = inputs[i];
          const val = String(input.value).trim();
          input.classList.toggle('is-invalid', visible && input.dataset.required === '1' && val === '');
          if (visible && val !== '') tokens.push(val);
        });
        hidden.value = tokens.join(' ');
        if (preview) preview.textContent = hidden.value === '' ? '(empty)' : hidden.value;
        // Not on first render - that isn't an edit (the Config page's
        // unsaved-changes badge listens for 'change').
        if (!initial) hidden.dispatchEvent(new Event('change', { bubbles: true }));
      }

      inputs.forEach(function (input) {
        input.addEventListener('input', function () { rebuild(false); });
        input.addEventListener('change', function () { rebuild(false); });
      });
      rebuild(true);
    });
  }

  // RTM mode checkboxes (formify "rtm_modes"): ticked modes -> RTVRTM's
  // single RTM code via the code table embedded next to them.
  function initRtmModeFields(root) {
    root.querySelectorAll('.rtm-modes-field').forEach(function (field) {
      const hidden = field.querySelector('input[type="hidden"][data-path]');
      const boxes = field.querySelectorAll('.rtm-mode-box');
      const summary = field.querySelector('.rtm-modes-summary');
      let codes = {};
      try {
        codes = JSON.parse(field.querySelector('.rtm-mode-codes').textContent);
      } catch (e) { return; }

      function recalc(initial) {
        const picked = [];
        boxes.forEach(function (cb) { if (cb.checked) picked.push(cb.value); });
        // On first render with an unrecognised stored code, leave it alone
        // (and its warning showing) until someone actually ticks a box.
        if (initial && picked.length === 0 && hidden.value !== '0') return;
        const code = picked.length ? codes[picked.join(',')] : 0;
        hidden.value = String(code);
        summary.textContent = code === 0
          ? 'No modes ticked - RTM is off (saved as 0).'
          : 'Players can vote to switch to any ticked mode (other than the one currently running). Saved as ' + code + '.';
        if (!initial) hidden.dispatchEvent(new Event('change', { bubbles: true }));
      }

      boxes.forEach(function (cb) { cb.addEventListener('change', function () { recalc(false); }); });
      recalc(true);
    });
  }

  function applyBoolAs(value, boolAs) {
    if (boolAs === 'int01') return value ? 1 : 0;
    if (boolAs === 'str01') return value ? '1' : '0';
    return value;
  }

  function readFieldValue(el) {
    const type = el.dataset.type;
    if (type === 'checkbox') {
      return { ok: true, value: applyBoolAs(el.checked, el.dataset.boolAs) };
    }
    if (type === 'bool_select') {
      return { ok: true, value: applyBoolAs(el.value === '1', el.dataset.boolAs) };
    }
    if (type === 'number') {
      return { ok: true, value: el.value === '' ? 0 : parseFloat(el.value) };
    }
    if (type === 'raw') {
      try {
        return { ok: true, value: JSON.parse(el.value) };
      } catch (e) {
        return { ok: false, path: el.dataset.path };
      }
    }
    return { ok: true, value: el.value };
  }

  // Reconstructs a full config object: deep-cloned `original` JSON plus
  // every [data-path] field under `root` plus every chip widget's live
  // list state (chipState, from initChipWidgets). Fields not present in
  // the DOM (e.g. a section this page doesn't render) are left untouched.
  function buildConfig(root, original, chipState) {
    const cfg = JSON.parse(JSON.stringify(original));
    let error = null;

    const badPart = root.querySelector('.composite-part.is-invalid');
    if (badPart) {
      const field = badPart.closest('.composite-field');
      const label = field ? field.querySelector('.form-label').textContent.trim() : 'a setting';
      return { cfg: cfg, error: '"' + label + '" has an empty number that it needs.' };
    }

    root.querySelectorAll('[data-path]').forEach(function (el) {
      if (error) return;
      const result = readFieldValue(el);
      if (!result.ok) {
        error = 'One of the raw-JSON fields (' + result.path + ') is not valid JSON.';
        return;
      }
      setPath(cfg, el.dataset.path, result.value);
    });

    if (chipState) {
      Object.keys(chipState).forEach(function (path) {
        setPath(cfg, path, chipState[path].slice());
      });
    }

    return { cfg: cfg, error: error };
  }

  return {
    setPath: setPath,
    initChipWidgets: initChipWidgets,
    initDependsOn: initDependsOn,
    initCompositeFields: initCompositeFields,
    initRtmModeFields: initRtmModeFields,
    buildConfig: buildConfig,
  };
})();
