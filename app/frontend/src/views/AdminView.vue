<template>
  <div>
    <h1>Admin Panel</h1>
    <div>
      <h2>Test Subscription</h2>
      <input v-model="twitchId" placeholder="Enter Twitch ID" />
      <button @click="testSubscription" :disabled="!twitchId.trim()">Test Subscription</button>
    </div>
    <div>
      <h2>Delete All Subscriptions</h2>
      <button @click="deleteAllSubscriptions">Delete All Subscriptions</button>
    </div>
    <div v-if="response">
      <h3>Response</h3>
      <pre>{{ response }}</pre>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      twitchId: "",
      response: null,
    };
  },
  methods: {
    async testSubscription() {
      try {
        this.response = null; // Reset response
        const res = await fetch(`/api/admin/test-subscription/${this.twitchId}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!res.ok) {
          throw new Error(`Error: ${res.statusText}`);
        }

        this.response = await res.json();
      } catch (error) {
        this.response = { success: false, error: error.message };
      }
    },
    async deleteAllSubscriptions() {
      try {
        this.response = null; // Reset response
        const res = await fetch("/api/admin/delete-all-subscriptions", {
          method: "DELETE",
        });

        if (!res.ok) {
          throw new Error(`Error: ${res.statusText}`);
        }

        this.response = await res.json();
      } catch (error) {
        this.response = { success: false, error: error.message };
      }
    },
  },
};
</script>

<style scoped>
h1 {
  text-align: center;
}
div {
  margin: 20px 0;
}
input {
  margin-right: 10px;
}
button {
  margin-top: 10px;
  cursor: pointer;
}
</style>
