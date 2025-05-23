<template>
  <div class="cleanup-policy-editor">
    <v-card variant="outlined" class="mb-4 pa-4">
      <v-card-title>{{ title }}</v-card-title>
      
      <v-form @submit.prevent>
        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="policy.type"
              :items="policyTypes"
              label="Cleanup Policy Type"
              :hint="policyHint"
              persistent-hint
            />
          </v-col>
          
          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="policy.threshold"
              type="number"
              :label="thresholdLabel"
              :hint="thresholdHint"
              persistent-hint
            />
          </v-col>
        </v-row>
        
        <v-row>
          <v-col cols="12" md="6">
            <v-switch
              v-model="policy.preserve_favorites"
              label="Preserve favorite categories"
              hint="Never delete recordings that belong to favorite categories"
              persistent-hint
            />
          </v-col>
          
          <v-col cols="12" md="6">
            <v-switch
              v-model="policy.delete_silently"
              label="Delete silently"
              hint="Delete without confirmation"
              persistent-hint
            />
          </v-col>
        </v-row>
        
        <v-row v-if="showPreserveCategories">
          <v-col cols="12">
            <v-autocomplete
              v-model="policy.preserve_categories"
              :items="availableCategories"
              label="Preserve specific categories"
              multiple
              chips
              hint="Never delete recordings from these categories"
              persistent-hint
            />
          </v-col>
        </v-row>
        
        <v-row v-if="showTimeframeControls">
          <v-col cols="12">
            <v-expansion-panels>
              <v-expansion-panel>
                <v-expansion-panel-title>
                  Advanced preservation rules
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-row>
                    <v-col cols="12" md="6">
                      <v-text-field
                        v-model="startDate"
                        type="date"
                        label="Preserve from date"
                      />
                    </v-col>
                    
                    <v-col cols="12" md="6">
                      <v-text-field
                        v-model="endDate"
                        type="date"
                        label="Preserve until date"
                      />
                    </v-col>
                  </v-row>
                  
                  <v-row>
                    <v-col cols="12">
                      <v-select
                        v-model="selectedWeekdays"
                        :items="weekdayOptions"
                        label="Preserve specific days of the week"
                        multiple
                        chips
                      />
                    </v-col>
                  </v-row>
                  
                  <v-row>
                    <v-col cols="12" md="6">
                      <v-text-field
                        v-model="startTime"
                        type="time"
                        label="Preserve from time"
                        hint="HH:MM format (24h)"
                        persistent-hint
                      />
                    </v-col>
                    
                    <v-col cols="12" md="6">
                      <v-text-field
                        v-model="endTime"
                        type="time"
                        label="Preserve until time"
                        hint="HH:MM format (24h)"
                        persistent-hint
                      />
                    </v-col>
                  </v-row>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-col>
        </v-row>
        
        <v-row>
          <v-col cols="12" class="d-flex justify-end">
            <v-btn 
              color="primary" 
              @click="savePolicy"
              :loading="isSaving"
            >
              Save Policy
            </v-btn>
          </v-col>
        </v-row>
      </v-form>
    </v-card>
    
    <v-card v-if="showStorageStats" variant="outlined" class="mb-4 pa-4">
      <v-card-title>Storage Statistics</v-card-title>
      
      <v-row>
        <v-col cols="12" md="6">
          <v-list>
            <v-list-item>
              <v-list-item-title>Total Size</v-list-item-title>
              <v-list-item-subtitle>{{ formatFileSize(storageStats.totalSize) }}</v-list-item-subtitle>
            </v-list-item>
            
            <v-list-item>
              <v-list-item-title>Recording Count</v-list-item-title>
              <v-list-item-subtitle>{{ storageStats.recordingCount }} recordings</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-col>
        
        <v-col cols="12" md="6">
          <v-list>
            <v-list-item>
              <v-list-item-title>Oldest Recording</v-list-item-title>
              <v-list-item-subtitle>{{ formatDate(storageStats.oldestRecording) }}</v-list-item-subtitle>
            </v-list-item>
            
            <v-list-item>
              <v-list-item-title>Newest Recording</v-list-item-title>
              <v-list-item-subtitle>{{ formatDate(storageStats.newestRecording) }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-col>
      </v-row>
      
      <v-row>
        <v-col cols="12" class="d-flex justify-end">
          <v-btn 
            color="error" 
            @click="runCleanup"
            :loading="isRunningCleanup"
            class="me-2"
          >
            Run Cleanup Now
          </v-btn>
          
          <v-btn 
            color="warning"  
            @click="runCustomCleanup"
            :loading="isRunningCleanup"
            :disabled="isSaving"
          >
            Test Current Policy
          </v-btn>
        </v-col>
      </v-row>
    </v-card>
    
    <v-snackbar v-model="showSnackbar" :color="snackbarColor">
      {{ snackbarText }}
      
      <template v-slot:actions>
        <v-btn 
          variant="text" 
          @click="showSnackbar = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
    
    <v-dialog v-model="showCleanupResults" max-width="700">
      <v-card>
        <v-card-title>Cleanup Results</v-card-title>
        
        <v-card-text>
          <p>{{ cleanupResults.message }}</p>
          
          <v-list v-if="cleanupResults.deleted_paths && cleanupResults.deleted_paths.length > 0">
            <v-list-subheader>Deleted Files:</v-list-subheader>
            <v-list-item 
              v-for="(path, index) in cleanupResults.deleted_paths" 
              :key="index"
            >
              <v-list-item-title>{{ path }}</v-list-item-title>
            </v-list-item>
          </v-list>
          
          <p v-else>No files were deleted.</p>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn 
            color="primary" 
            @click="showCleanupResults = false"
          >
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { CleanupPolicyType } from '@/types/recording';
import { useRecordingSettings } from '@/composables/useRecordingSettings';

const recordingSettings = useRecordingSettings();

const props = defineProps({
  streamerId: {
    type: Number,
    required: false
  },
  title: {
    type: String,
    default: 'Cleanup Policy Settings'
  },
  isGlobal: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['saved', 'updated']);

// State
const isSaving = ref(false);
const isRunningCleanup = ref(false);
const showSnackbar = ref(false);
const snackbarText = ref('');
const snackbarColor = ref('success');
const showCleanupResults = ref(false);
const cleanupResults = ref({
  message: '',
  deleted_count: 0,
  deleted_paths: [] as string[]
});

// Storage stats
const showStorageStats = ref(false);
const storageStats = ref({
  totalSize: 0,
  recordingCount: 0,
  oldestRecording: '',
  newestRecording: ''
});

// Base policy
const policy = ref({
  type: CleanupPolicyType.COUNT,
  threshold: 10,
  preserve_favorites: true,
  preserve_categories: [] as string[],
  preserve_timeframe: {
    start_date: '',
    end_date: '',
    weekdays: [] as number[],
    timeOfDay: {
      start: '',
      end: ''
    }
  },
  delete_silently: false
});

// Form fields for the timeframe
const startDate = ref('');
const endDate = ref('');
const selectedWeekdays = ref<number[]>([]);
const startTime = ref('');
const endTime = ref('');

// Options
const policyTypes = [
  { title: 'Limit by Count', value: CleanupPolicyType.COUNT },
  { title: 'Limit by Size (GB)', value: CleanupPolicyType.SIZE },
  { title: 'Limit by Age (days)', value: CleanupPolicyType.AGE }
];

const weekdayOptions = [
  { title: 'Sunday', value: 0 },
  { title: 'Monday', value: 1 },
  { title: 'Tuesday', value: 2 },
  { title: 'Wednesday', value: 3 },
  { title: 'Thursday', value: 4 },
  { title: 'Friday', value: 5 },
  { title: 'Saturday', value: 6 }
];

const availableCategories = ref<string[]>([]);

// Computed properties
const policyHint = computed(() => {
  switch (policy.value.type) {
    case CleanupPolicyType.COUNT:
      return 'Keep only the most recent X recordings';
    case CleanupPolicyType.SIZE:
      return 'Limit total storage to X gigabytes';
    case CleanupPolicyType.AGE:
      return 'Delete recordings older than X days';
    default:
      return '';
  }
});

const thresholdLabel = computed(() => {
  switch (policy.value.type) {
    case CleanupPolicyType.COUNT:
      return 'Number of recordings to keep';
    case CleanupPolicyType.SIZE:
      return 'Maximum storage size (GB)';
    case CleanupPolicyType.AGE:
      return 'Maximum age (days)';
    default:
      return 'Threshold';
  }
});

const thresholdHint = computed(() => {
  switch (policy.value.type) {
    case CleanupPolicyType.COUNT:
      return 'Oldest recordings will be deleted when this limit is exceeded';
    case CleanupPolicyType.SIZE:
      return 'Oldest recordings will be deleted when total size exceeds this limit';
    case CleanupPolicyType.AGE:
      return 'Recordings older than this many days will be deleted';
    default:
      return '';
  }
});

const showPreserveCategories = computed(() => true);
const showTimeframeControls = computed(() => true);

// Watchers
watch([startDate, endDate, selectedWeekdays, startTime, endTime], () => {
  updateTimeframeFromFields();
});

// Methods
function updateTimeframeFromFields() {
  policy.value.preserve_timeframe = {
    start_date: startDate.value,
    end_date: endDate.value,
    weekdays: selectedWeekdays.value,
    timeOfDay: {
      start: startTime.value,
      end: endTime.value
    }
  };
}

function updateFieldsFromTimeframe() {
  const timeframe = policy.value.preserve_timeframe;
  
  startDate.value = timeframe.start_date || '';
  endDate.value = timeframe.end_date || '';
  selectedWeekdays.value = timeframe.weekdays || [];
  
  if (timeframe.timeOfDay) {
    startTime.value = timeframe.timeOfDay.start || '';
    endTime.value = timeframe.timeOfDay.end || '';
  } else {
    startTime.value = '';
    endTime.value = '';
  }
}

async function loadPolicy() {
  try {
    const defaultPolicy = recordingSettings.getDefaultCleanupPolicy();
    
    if (props.isGlobal) {
      // Load global settings
      await recordingSettings.fetchSettings();
      if (recordingSettings.settings.value?.cleanup_policy) {
        policy.value = {
          ...defaultPolicy,
          ...recordingSettings.settings.value.cleanup_policy,
          preserve_favorites: recordingSettings.settings.value.cleanup_policy.preserve_favorites ?? true,
          preserve_categories: recordingSettings.settings.value.cleanup_policy.preserve_categories ?? [],
          preserve_timeframe: {
            start_date: recordingSettings.settings.value.cleanup_policy.preserve_timeframe?.start_date ?? '',
            end_date: recordingSettings.settings.value.cleanup_policy.preserve_timeframe?.end_date ?? '',
            weekdays: recordingSettings.settings.value.cleanup_policy.preserve_timeframe?.weekdays ?? [],
            timeOfDay: {
              start: recordingSettings.settings.value.cleanup_policy.preserve_timeframe?.timeOfDay?.start ?? '',
              end: recordingSettings.settings.value.cleanup_policy.preserve_timeframe?.timeOfDay?.end ?? ''
            }
          },
          delete_silently: recordingSettings.settings.value.cleanup_policy.delete_silently ?? false
        };
      } else {
        policy.value = defaultPolicy;
      }
    } else if (props.streamerId) {
      // Load streamer-specific settings
      await recordingSettings.fetchStreamerSettings();
      const streamerSettings = recordingSettings.streamerSettings.value.find(
        s => s.streamer_id === props.streamerId
      );
      
      if (streamerSettings?.cleanup_policy) {
        policy.value = {
          ...defaultPolicy,
          ...streamerSettings.cleanup_policy,
          preserve_favorites: streamerSettings.cleanup_policy.preserve_favorites ?? true,
          preserve_categories: streamerSettings.cleanup_policy.preserve_categories ?? [],
          preserve_timeframe: {
            start_date: streamerSettings.cleanup_policy.preserve_timeframe?.start_date ?? '',
            end_date: streamerSettings.cleanup_policy.preserve_timeframe?.end_date ?? '',
            weekdays: streamerSettings.cleanup_policy.preserve_timeframe?.weekdays ?? [],
            timeOfDay: {
              start: streamerSettings.cleanup_policy.preserve_timeframe?.timeOfDay?.start ?? '',
              end: streamerSettings.cleanup_policy.preserve_timeframe?.timeOfDay?.end ?? ''
            }
          },
          delete_silently: streamerSettings.cleanup_policy.delete_silently ?? false
        };
      } else {
        policy.value = defaultPolicy;
      }
      
      // Load storage stats for this streamer
      await loadStorageStats();
    }    
    // Update form fields from the loaded policy
    updateFieldsFromTimeframe();
    
    // Load available categories
    await loadAvailableCategories();
    
  } catch (error) {
    showError('Failed to load cleanup policy settings');
    console.error('Error loading policy:', error);
  }
}

async function loadAvailableCategories() {
  try {
    // Fetch available categories from the API
    const categories = await recordingSettings.getAvailableCategories();
    availableCategories.value = categories.map(category => category.name);
  } catch (error) {
    console.error('Error loading categories:', error);
  }
}

async function loadStorageStats() {
  if (!props.streamerId) return;
  
  try {
    showStorageStats.value = true;
    const stats = await recordingSettings.getStreamerStorageUsage(props.streamerId);
    storageStats.value = stats;
  } catch (error) {
    console.error('Error loading storage stats:', error);
  }
}

async function savePolicy() {
  try {
    isSaving.value = true;
    
    // Update timeframe from form fields one more time before saving
    updateTimeframeFromFields();
    
    // Ensure all required properties are present
    const completePolicy = {
      type: policy.value.type,
      threshold: policy.value.threshold,
      preserve_favorites: policy.value.preserve_favorites !== undefined ? policy.value.preserve_favorites : true,
      preserve_categories: policy.value.preserve_categories || [],
      preserve_timeframe: {
        start_date: policy.value.preserve_timeframe?.start_date || '',
        end_date: policy.value.preserve_timeframe?.end_date || '',
        weekdays: policy.value.preserve_timeframe?.weekdays || [],
        timeOfDay: {
          start: policy.value.preserve_timeframe?.timeOfDay?.start || '',
          end: policy.value.preserve_timeframe?.timeOfDay?.end || ''
        }
      },
      delete_silently: policy.value.delete_silently !== undefined ? policy.value.delete_silently : false
    };
    
    if (props.isGlobal) {
      // Update global policy
      await recordingSettings.updateCleanupPolicy(completePolicy);
    } else if (props.streamerId) {
      // Update streamer-specific policy
      await recordingSettings.updateStreamerCleanupPolicy(props.streamerId, completePolicy);
    }
    
    showSuccess('Cleanup policy saved successfully');
    emit('saved', completePolicy);
  } catch (error) {
    showError('Failed to save cleanup policy');
    console.error('Error saving policy:', error);
  } finally {
    isSaving.value = false;
  }
}

async function runCleanup() {
  if (!props.streamerId) return;
  
  try {
    isRunningCleanup.value = true;
    
    const result = await recordingSettings.cleanupOldRecordings(props.streamerId);
    
    if (result) {
      // Refresh storage stats
      await loadStorageStats();
      showSuccess('Cleanup completed successfully');
    } else {
      showError('Cleanup failed');
    }
  } catch (error) {
    showError('Error running cleanup');
    console.error('Error running cleanup:', error);
  } finally {
    isRunningCleanup.value = false;
  }
}

async function runCustomCleanup() {
  if (!props.streamerId) return;
  
  try {
    isRunningCleanup.value = true;
    
    // Update timeframe from form fields before running custom cleanup
    updateTimeframeFromFields();
    
    // Ensure all required properties are present
    const completePolicy = {
      type: policy.value.type,
      threshold: policy.value.threshold,
      preserve_favorites: policy.value.preserve_favorites !== undefined ? policy.value.preserve_favorites : true,
      preserve_categories: policy.value.preserve_categories || [],
      preserve_timeframe: {
        start_date: policy.value.preserve_timeframe?.start_date || '',
        end_date: policy.value.preserve_timeframe?.end_date || '',
        weekdays: policy.value.preserve_timeframe?.weekdays || [],
        timeOfDay: {
          start: policy.value.preserve_timeframe?.timeOfDay?.start || '',
          end: policy.value.preserve_timeframe?.timeOfDay?.end || ''
        }
      },
      delete_silently: policy.value.delete_silently !== undefined ? policy.value.delete_silently : false
    };
    
    const result = await recordingSettings.runCustomCleanup(props.streamerId, completePolicy);
    
    // Show results dialog
    cleanupResults.value = {
      message: `Deleted ${result.deletedCount} recordings`,
      deleted_count: result.deletedCount,
      deleted_paths: result.deletedPaths
    };
    showCleanupResults.value = true;
    
    // Refresh storage stats
    await loadStorageStats();
    
  } catch (error) {
    showError('Error running custom cleanup');
    console.error('Error running custom cleanup:', error);
  } finally {
    isRunningCleanup.value = false;
  }
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(isoDate: string): string {
  if (!isoDate) return 'N/A';
  
  try {
    return new Date(isoDate).toLocaleString();
  } catch (error) {
    return 'Invalid date';
  }
}

function showSuccess(message: string) {
  snackbarText.value = message;
  snackbarColor.value = 'success';
  showSnackbar.value = true;
}

function showError(message: string) {
  snackbarText.value = message;
  snackbarColor.value = 'error';
  showSnackbar.value = true;
}

// Load initial data
onMounted(() => {
  loadPolicy();
});
</script>

<style scoped>
.cleanup-policy-editor {
  max-width: 100%;
}
</style>
