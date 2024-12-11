<template>
  <div class="streamer-form">
    <input v-model="username" placeholder="Enter streamer username" />
    <button @click="addStreamer">Add Streamer</button>
  </div>
</template>

<script>
export default {
  data() {
    return {
      username: ''
    }
  },
  methods: {
    async addStreamer() {
      try {
        const response = await fetch(`/api/streamers/${this.username}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        const data = await response.json();
        if (data.success) {
          this.$emit('streamer-added');
          this.username = '';
        }
      } catch (error) {
        console.error('Error adding streamer:', error);
      }
    }
  }
}
</script>

<style scoped>
.streamer-form {
  margin: 1rem 0;
}
</style>
