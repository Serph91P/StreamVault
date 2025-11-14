# Add Streamer Modal Polish & UX Improvements

## 🟢 Priority: MEDIUM
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 2-3 hours  
**Sprint:** Sprint 3: Polish & Enhancements  
**Impact:** MEDIUM - User experience polish

---

## 📝 Problem Description

### Current State: Modal Lacks Visual Clarity

**Issues Identified:**
- ❌ **Username input lacks icon** - No visual indicator for input type
- ❌ **OR divider low contrast** - Hard to distinguish between manual entry and callback import
- ❌ **Callback URL container narrow on mobile** - URL gets truncated, hard to read
- ❌ **No validation feedback while typing** - User doesn't know if input is valid until submit
- ❌ **Success/error states not prominent** - Feedback messages easy to miss

**User Impact:**
- Users unclear which field to enter username
- Confusion between "Add by username" vs "Import from callback"
- Can't see full callback URL on mobile (truncated)
- Must wait for submit to see validation errors
- Miss success/error messages after adding streamer

**Current Modal Structure:**
```
┌───────────────────────────────┐
│   Add Streamer                │
├───────────────────────────────┤
│                               │
│ [ Username input ]  ← No icon │
│                               │
│ ─────── OR ───────  ← Low contrast
│                               │
│ [ Callback URL ]    ← Narrow  │
│ http://localhost... (truncated)
│                               │
│ [Cancel]  [Add Streamer]      │
└───────────────────────────────┘
```

**Desired User Experience:**
- Clear visual distinction between input methods
- Obvious which field is for username
- Full callback URL visible (especially on mobile)
- Real-time validation feedback (checkmark or error while typing)
- Prominent success/error messages after action

---

## 🎯 Requirements

### 1. Username Input Enhancements

**Visual Indicators:**
- **Icon:** User icon (👤) on the left side of input
- **Status icon:** Right side shows validation state:
  - ⏳ Spinner while checking
  - ✓ Green checkmark if valid
  - ✕ Red X if invalid
- **Border color:** Changes based on validation state (green/red)

**Validation Rules:**
- **Format:** 4-25 characters, alphanumeric + underscore only
- **Pattern:** `/^[a-zA-Z0-9_]{4,25}$/`
- **Timing:** Validate after 500ms typing pause (debounce)
- **Check existence:** API call to verify streamer not already added

**Validation Messages:**
```
✓ Valid username
✕ Username must be 4-25 characters (letters, numbers, underscore)
✕ Username already added
✕ Twitch user not found
```

### 2. OR Divider Enhancement

**Current State:**
- Gray line with gray text "OR"
- Low contrast against background

**Required State:**
- **Line:** Higher contrast border color
- **Background:** Solid background behind "OR" text (not transparent)
- **Text:** Bolder font weight, higher contrast color
- **Spacing:** 24px vertical margin above/below

**Visual Design:**
```
────────────────────────
      [ OR ]       ← Bold text on solid background
────────────────────────
```

### 3. Callback URL Container (Mobile)

**Current State:**
- Fixed width container (300px?)
- URL truncated with ellipsis (http://localhost...)
- Hard to see full URL on mobile

**Required State:**
- **Mobile (< 768px):** Full viewport width minus padding
- **Copy button:** Large touch target (48x48px)
- **URL display:** Monospace font, scrollable horizontally if needed
- **Visual feedback:** Copy button shows "Copied!" tooltip

**Layout on Mobile:**
```
┌─────────────────────────────────────┐
│ Callback URL:                       │
│ ┌─────────────────────────────────┐ │
│ │ http://localhost:8000/api/...   │ │  ← Scrollable
│ │                        [Copy] 📋│ │  ← 48px button
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### 4. Live Validation Feedback

**Debounced Validation:**
- Wait 500ms after last keystroke before validating
- Show spinner during validation
- Update status icon when validation completes

**Visual States:**
- **Empty:** No icon, normal border
- **Typing:** No feedback (waiting for debounce)
- **Validating:** Spinner icon on right, normal border
- **Valid:** Green checkmark, green border, success message
- **Invalid:** Red X, red border, error message

**State Transitions:**
```
Empty → Typing (500ms debounce) → Validating (API call) → Valid/Invalid
```

### 5. Success/Error Messages

**Current State:**
- Small text below form
- Easy to overlook

**Required State:**
- **Alert box:** Colored background with icon
- **Position:** Top of modal, full width
- **Animation:** Slide down when shown, fade out after 5s
- **Dismissible:** X button to close manually

**Alert Types:**
```
✅ Success: Streamer "username" added successfully
❌ Error: Failed to add streamer - [reason]
⚠️ Warning: Streamer already exists
```

---

## 📐 Modal Layout (Mobile vs Desktop)

### Desktop Layout (≥ 768px)

```
┌──────────────────────────────────────────┐
│ Add Streamer                        [X]  │
├──────────────────────────────────────────┤
│ [✅ Success message if shown]           │
│                                          │
│ Twitch Username:                         │
│ [👤] [Input field...     ] [✓]          │
│ ✓ Valid username                         │
│                                          │
│ ─────────── OR ─────────── (bold)        │
│                                          │
│ Import from EventSub Callback:           │
│ [Callback URL display] [Copy 📋]         │
│                                          │
│         [Cancel]  [Add Streamer]         │
└──────────────────────────────────────────┘
```

### Mobile Layout (< 768px)

```
┌──────────────────────────────────────┐
│ Add Streamer                    [X]  │
├──────────────────────────────────────┤
│ [✅ Success message]                │
│                                      │
│ Twitch Username:                     │
│ [👤] [Input...    ] [✓]             │
│ ✓ Valid                              │
│                                      │
│ ────── OR ────── (bold, high contrast)
│                                      │
│ Callback URL:                        │
│ ┌──────────────────────────────┐    │
│ │ http://localhost:800...      │    │
│ │                    [Copy 📋] │    │  ← Full width
│ └──────────────────────────────┘    │
│                                      │
│ [Cancel]         [Add Streamer]     │  ← Full width buttons
└──────────────────────────────────────┘
```

---

## 🎨 Design Requirements

### 1. Input Icon Sizing

**User Icon (Left Side):**
- Size: 20px (desktop), 24px (mobile)
- Position: 12px from left edge (16px on mobile)
- Color: `var(--text-secondary)` (gray)

**Status Icon (Right Side):**
- Size: 20px (desktop), 24px (mobile)
- Position: 12px from right edge (16px on mobile)
- Colors:
  - Spinner: `var(--text-secondary)` with animation
  - Checkmark: `var(--success-color)` (green)
  - Error X: `var(--danger-color)` (red)

### 2. Input Border States

**Normal:**
- Border: `1px solid var(--border-color)`
- Background: `var(--bg-secondary)`

**Valid:**
- Border: `2px solid var(--success-color)` (green)
- Background: `rgba(var(--success-rgb), 0.05)` (subtle green tint)

**Invalid:**
- Border: `2px solid var(--danger-color)` (red)
- Background: `rgba(var(--danger-rgb), 0.05)` (subtle red tint)

**Focus:**
- Border: `2px solid var(--primary-color)` (blue)
- Outline: None (remove default browser outline)

### 3. OR Divider Styling

**Line:**
- Height: 1px
- Color: `var(--border-color)` with 50% opacity increase
- Width: Full width minus 40px margin on each side

**Text:**
- Font-weight: 600 (semi-bold)
- Font-size: 14px
- Color: `var(--text-primary)` (higher contrast)
- Background: `var(--bg-primary)` (solid, not transparent)
- Padding: 0 12px (space around text)

### 4. Callback URL Container

**Container:**
- Background: `var(--bg-tertiary)` (darker)
- Border: `1px solid var(--border-color)`
- Border-radius: `var(--border-radius-md)`
- Padding: 12px

**URL Text:**
- Font-family: `monospace` (code font)
- Font-size: 14px (12px on mobile if needed)
- Color: `var(--text-primary)`
- Overflow: `auto` (horizontal scroll if truncated)
- White-space: `nowrap` (don't wrap)

**Copy Button:**
- Size: 48x48px on mobile, 36px on desktop
- Position: Right side of container
- Icon: Clipboard (📋)
- Tooltip: "Copied!" (shows for 2s after click)

### 5. Alert Messages

**Success Alert:**
- Background: `rgba(var(--success-rgb), 0.1)`
- Border-left: `4px solid var(--success-color)`
- Icon: Checkmark (✓)

**Error Alert:**
- Background: `rgba(var(--danger-rgb), 0.1)`
- Border-left: `4px solid var(--danger-color)`
- Icon: Error X (✕)

**Animation:**
- Slide down from top: 300ms ease-out
- Auto-dismiss after 5 seconds: Fade out 300ms
- Dismiss button: X on right side (24x24px)

---

## 📋 Implementation Scope

### Files to Modify

**Primary Component:**
- `app/frontend/src/components/AddStreamerModal.vue` (or similar)
- `app/frontend/src/views/AddStreamerView.vue` (if separate)

**What Needs Changing:**
1. **Username Input Markup** - Add icon, status icon, validation states
2. **Validation Logic** - Debounced validation, API existence check
3. **OR Divider SCSS** - Increase contrast, bold text, solid background
4. **Callback URL Container** - Full-width on mobile, copy button
5. **Alert Component** - Success/error messages with animation

**Composables to Create/Update:**
- `useUsernameValidation.ts` - Debounced validation logic
- `useClipboard.ts` - Copy to clipboard with feedback

---

## ✅ Acceptance Criteria

### Username Input
- [ ] User icon visible on left side (24px on mobile)
- [ ] Status icon visible on right side (✓, ✕, or spinner)
- [ ] Border color changes based on validation state
- [ ] Validation runs after 500ms typing pause
- [ ] Success message: "✓ Valid username"
- [ ] Error message shows specific reason (format, already exists, not found)

### OR Divider
- [ ] Line has higher contrast against background
- [ ] Text is bold (font-weight 600)
- [ ] Solid background behind "OR" text
- [ ] 24px vertical margin above/below

### Callback URL Container
- [ ] Full viewport width on mobile (< 768px)
- [ ] URL displayed in monospace font
- [ ] Copy button 48x48px on mobile
- [ ] "Copied!" tooltip shows after click (2s duration)
- [ ] Horizontal scroll if URL too long

### Live Validation
- [ ] No validation feedback while actively typing
- [ ] Spinner shows during API check
- [ ] Checkmark appears when valid
- [ ] Error X appears when invalid
- [ ] Border and background color match state

### Alert Messages
- [ ] Success alert appears after adding streamer
- [ ] Error alert appears if add fails
- [ ] Alert slides down from top (300ms)
- [ ] Alert auto-dismisses after 5 seconds
- [ ] Dismiss button (X) works manually

### Mobile Responsiveness (< 768px)
- [ ] Modal fits viewport width
- [ ] Callback URL container full-width
- [ ] Copy button touch-friendly (48px)
- [ ] Buttons full-width or stacked
- [ ] All text readable without zoom

### Testing Checklist
- [ ] Enter valid username → Checkmark appears
- [ ] Enter invalid username → Error message shown
- [ ] Enter existing streamer → "Already added" error
- [ ] Copy callback URL → "Copied!" tooltip shows
- [ ] Submit form → Success alert appears
- [ ] Test on iPhone SE (375px width)
- [ ] Test on desktop (1280px width)
- [ ] Keyboard navigation works (Tab, Enter)

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Alert patterns, form validation states, icons
- `.github/instructions/frontend.instructions.md` - Form patterns, debouncing

**Validation Libraries:**
- Vue Composition API: `useDebounceFn()` from VueUse
- Regex pattern for Twitch usernames: `/^[a-zA-Z0-9_]{4,25}$/`

**Related Issues:**
- Issue #4: Settings Tables Mobile (similar form input patterns)
- Issue #11: Streamer Cards (similar touch targets for buttons)

**Icon Libraries:**
- Check current icon system (Font Awesome, Material Icons, or custom)
- Icons needed: user (👤), checkmark (✓), error (✕), spinner (⏳), clipboard (📋)

---

## 🎯 Solution

### Polish Improvements

1. **Username Input Icon** - Add user icon for clarity
2. **OR Divider** - Increase visual contrast
3. **Callback URL Container** - Full-width on mobile
4. **Live Validation** - Show checkmark/error while typing
5. **Better Error Messages** - Actionable feedback

---

## 📋 Implementation Tasks

### 1. Username Input with Icon (30 minutes)

```vue
<template>
  <div class="form-group">
    <label for="username-input" class="form-label">
      Twitch Username
    </label>
    
    <div class="input-with-icon">
      <i class="icon-user input-icon"></i>
      <input
        id="username-input"
        v-model="username"
        type="text"
        class="form-input"
        :class="{ 'is-valid': isValid, 'is-invalid': isInvalid }"
        placeholder="Enter Twitch username"
        @input="handleInput"
      />
      
      <div class="input-status" v-if="username">
        <i v-if="isValid" class="icon-check text-success"></i>
        <i v-else-if="isInvalid" class="icon-close text-danger"></i>
        <i v-else class="icon-spinner spinning"></i>
      </div>
    </div>
    
    <p v-if="validationMessage" class="form-help" :class="helpClass">
      {{ validationMessage }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const username = ref('')
const isValidating = ref(false)
const isValid = ref(false)
const isInvalid = ref(false)
const validationMessage = ref('')

const helpClass = computed(() => ({
  'text-success': isValid.value,
  'text-danger': isInvalid.value,
  'text-secondary': !isValid.value && !isInvalid.value
}))

const handleInput = async () => {
  if (!username.value) {
    isValid.value = false
    isInvalid.value = false
    validationMessage.value = ''
    return
  }
  
  // Basic validation: alphanumeric + underscore
  const isValidFormat = /^[a-zA-Z0-9_]{4,25}$/.test(username.value)
  
  if (!isValidFormat) {
    isInvalid.value = true
    isValid.value = false
    validationMessage.value = 'Username must be 4-25 characters (letters, numbers, underscore)'
    return
  }
  
  // Check if already exists
  isValidating.value = true
  
  // ... API call to check if streamer exists ...
  
  isValidating.value = false
  isValid.value = true
  validationMessage.value = '✓ Valid username'
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.input-with-icon {
  position: relative;
  display: flex;
  align-items: center;
  
  .input-icon {
    position: absolute;
    left: 12px;
    font-size: 18px;
    color: var(--text-secondary);
    pointer-events: none;
    
    @include m.respond-below('md') {
      left: 16px;
      font-size: 20px;
    }
  }
  
  .form-input {
    flex: 1;
    padding-left: 42px; // Make room for icon
    padding-right: 42px; // Make room for status
    
    @include m.respond-below('md') {
      padding-left: 48px;
      padding-right: 48px;
    }
    
    &.is-valid {
      border-color: var(--success-color);
    }
    
    &.is-invalid {
      border-color: var(--danger-color);
    }
  }
  
  .input-status {
    position: absolute;
    right: 12px;
    font-size: 18px;
    
    @include m.respond-below('md') {
      right: 16px;
      font-size: 20px;
    }
    
    .spinning {
      animation: spin 1s linear infinite;
    }
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.form-help {
  margin-top: 6px;
  font-size: 13px;
  
  @include m.respond-below('md') {
    font-size: 14px;
  }
}
</style>
```

---

### 2. Enhanced OR Divider (20 minutes)

```vue
<template>
  <div class="or-divider">
    <span class="or-line"></span>
    <span class="or-text">OR</span>
    <span class="or-line"></span>
  </div>
</template>

<style scoped lang="scss">
.or-divider {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 32px 0;
  
  .or-line {
    flex: 1;
    height: 2px;
    background: linear-gradient(
      to right,
      transparent,
      var(--border-color) 20%,
      var(--border-color) 80%,
      transparent
    );
  }
  
  .or-text {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 2px;
    padding: 8px 16px;
    background: var(--bg-tertiary);
    border-radius: var(--border-radius-full);
    border: 2px solid var(--border-color);
    
    @include m.respond-below('md') {
      font-size: 15px;
      padding: 10px 20px;
    }
  }
}
</style>
```

---

### 3. Callback URL Container Mobile (30 minutes)

```vue
<template>
  <div class="callback-url-section">
    <h3>Import via Callback URL</h3>
    <p class="section-description">
      Use StreamVault's callback URL to automatically add streamers when you subscribe on Twitch.
    </p>
    
    <div class="callback-url-container">
      <div class="url-display">
        <code>{{ callbackUrl }}</code>
      </div>
      
      <button 
        class="btn btn-secondary copy-btn"
        @click="copyToClipboard"
      >
        <i :class="copied ? 'icon-check' : 'icon-copy'"></i>
        {{ copied ? 'Copied!' : 'Copy' }}
      </button>
    </div>
    
    <div class="help-text">
      <i class="icon-info-circle"></i>
      <p>
        Paste this URL in your Twitch subscription webhook to automatically track streamers.
        <a href="/docs/callback-setup" target="_blank">Setup Guide</a>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const copied = ref(false)
const callbackUrl = computed(() => {
  const baseUrl = window.location.origin
  return `${baseUrl}/api/webhooks/twitch/callback`
})

const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(callbackUrl.value)
    copied.value = true
    
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.callback-url-section {
  margin-top: 24px;
  
  h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
  }
  
  .section-description {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 16px;
    line-height: 1.5;
  }
}

.callback-url-container {
  display: flex;
  gap: 12px;
  
  @include m.respond-below('md') {
    flex-direction: column;
  }
  
  .url-display {
    flex: 1;
    padding: 12px 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius-md);
    overflow-x: auto;
    
    @include m.respond-below('md') {
      // Full width on mobile
      width: 100%;
      padding: 16px;
    }
    
    code {
      font-family: 'Courier New', monospace;
      font-size: 13px;
      color: var(--text-primary);
      word-break: break-all;
      
      @include m.respond-below('md') {
        font-size: 14px;
      }
    }
  }
  
  .copy-btn {
    flex-shrink: 0;
    min-width: 100px;
    
    @include m.respond-below('md') {
      width: 100%;
      min-height: 48px;
    }
    
    i {
      margin-right: 6px;
    }
  }
}

.help-text {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-info);
  border-radius: var(--border-radius-md);
  border-left: 3px solid var(--info-color);
  
  i {
    font-size: 20px;
    color: var(--info-color);
    flex-shrink: 0;
  }
  
  p {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.5;
    
    @include m.respond-below('md') {
      font-size: 14px;
    }
    
    a {
      color: var(--info-color);
      text-decoration: none;
      font-weight: 600;
      
      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>
```

---

### 4. Better Error Messages (30 minutes)

```vue
<script setup lang="ts">
const errorMessages = {
  'invalid_username': {
    title: 'Invalid Username',
    message: 'Username must be 4-25 characters (letters, numbers, underscore)',
    icon: 'icon-alert-circle'
  },
  'streamer_exists': {
    title: 'Streamer Already Added',
    message: 'This streamer is already in your list. Check the Home page.',
    icon: 'icon-info-circle'
  },
  'streamer_not_found': {
    title: 'Streamer Not Found',
    message: 'Could not find this Twitch channel. Check the spelling.',
    icon: 'icon-search'
  },
  'network_error': {
    title: 'Network Error',
    message: 'Could not connect to Twitch. Check your internet connection.',
    icon: 'icon-wifi-off'
  }
}

const showError = (errorType: keyof typeof errorMessages) => {
  const error = errorMessages[errorType]
  
  // Show toast or alert
  toast.error(`${error.title}: ${error.message}`)
}
</script>
```

---

### 5. Success State Animation (20 minutes)

```vue
<template>
  <transition name="success">
    <div v-if="showSuccess" class="success-message">
      <div class="success-icon">
        <i class="icon-check-circle"></i>
      </div>
      <div class="success-content">
        <h3>Streamer Added!</h3>
        <p>{{ streamerName }} has been added to your list.</p>
      </div>
      <button class="btn btn-primary" @click="goToHome">
        View Streamers
      </button>
    </div>
  </transition>
</template>

<style scoped lang="scss">
.success-message {
  padding: 32px;
  text-align: center;
  background: var(--bg-success);
  border: 2px solid var(--success-color);
  border-radius: var(--border-radius-lg);
  
  .success-icon {
    i {
      font-size: 64px;
      color: var(--success-color);
    }
  }
  
  .success-content {
    margin: 20px 0;
    
    h3 {
      font-size: 24px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 8px;
    }
    
    p {
      font-size: 16px;
      color: var(--text-secondary);
    }
  }
}

.success-enter-active {
  animation: bounceIn 0.6s;
}

@keyframes bounceIn {
  0% { opacity: 0; transform: scale(0.3); }
  50% { opacity: 1; transform: scale(1.05); }
  70% { transform: scale(0.9); }
  100% { transform: scale(1); }
}
</style>
```

---

## 📂 Files to Modify

- `app/frontend/src/views/AddStreamerView.vue`
- `app/frontend/src/components/AddStreamerForm.vue`
- `app/frontend/src/components/TwitchImportForm.vue`

---

## ✅ Acceptance Criteria

**Username Input:**
- [ ] User icon visible on left side
- [ ] Live validation while typing
- [ ] Checkmark when valid
- [ ] Error icon when invalid
- [ ] Helpful error messages

**OR Divider:**
- [ ] Clearly visible separation
- [ ] Gradient lines from transparent to solid
- [ ] OR text in rounded pill
- [ ] Higher contrast than before

**Callback URL:**
- [ ] Full-width container on mobile
- [ ] Easy to copy (one-tap copy button)
- [ ] Copy feedback ("Copied!")
- [ ] Help text with setup guide link

**Error Handling:**
- [ ] Specific error messages
- [ ] Icons for error types
- [ ] Actionable suggestions
- [ ] Not generic "Error occurred"

**Success State:**
- [ ] Animated success message
- [ ] Streamer name displayed
- [ ] Quick link to view streamers
- [ ] Celebration feel

---

## 🧪 Testing Checklist

**Validation:**
- [ ] Type valid username → Checkmark appears
- [ ] Type invalid username → Error message
- [ ] Type existing streamer → "Already added" message
- [ ] Type non-existent streamer → "Not found" message

**Callback URL:**
- [ ] Copy button works
- [ ] "Copied!" feedback shown
- [ ] URL correct (includes domain)
- [ ] Container full-width on mobile (< 768px)

**Error Messages:**
- [ ] Network error → Helpful message
- [ ] Invalid format → Format requirements shown
- [ ] Already exists → Link to home page
- [ ] Not found → Spelling suggestion

**Success State:**
- [ ] Success message animates in
- [ ] Streamer name shown
- [ ] "View Streamers" button works
- [ ] Animation smooth (no jank)

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md`  
**Related:** `docs/REMAINING_FRONTEND_TASKS.md`  
**Design:** `docs/DESIGN_SYSTEM.md`

---

## 🤖 Copilot Instructions

**Context:**
Polish Add Streamer modal with username input icon, better OR divider, full-width callback URL on mobile, live validation, and better error messages.

**Critical Patterns:**

1. **Input with icon:**
   ```vue
   <div class="input-with-icon">
     <i class="icon-user input-icon"></i>
     <input class="form-input" />
     <div class="input-status"><i class="icon-check"></i></div>
   </div>
   ```

2. **Live validation:**
   ```typescript
   const isValidFormat = /^[a-zA-Z0-9_]{4,25}$/.test(username.value)
   ```

3. **Copy to clipboard:**
   ```typescript
   await navigator.clipboard.writeText(url)
   ```

4. **Success animation:**
   ```scss
   @keyframes bounceIn {
     0% { transform: scale(0.3); }
     100% { transform: scale(1); }
   }
   ```

**Implementation Order:**
1. Add username input icon and validation
2. Enhance OR divider styling
3. Make callback URL container full-width on mobile
4. Improve error messages with specific types
5. Add success state animation

**Testing Strategy:**
1. Test validation with various inputs
2. Verify copy to clipboard
3. Test on mobile (< 768px)
4. Verify error messages actionable
5. Check success animation smooth

**Files to Read First:**
- `app/frontend/src/views/AddStreamerView.vue`
- `docs/DESIGN_SYSTEM.md` (form patterns)

**Success Criteria:**
Username input has icon, live validation works, OR divider prominent, callback URL full-width mobile, errors specific, success animated.

**Common Pitfalls:**
- ❌ Clipboard API not checking browser support
- ❌ Validation too aggressive (triggers immediately)
- ❌ OR divider still low contrast
- ❌ Missing mobile breakpoint for callback URL
- ❌ Generic error messages
