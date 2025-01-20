<template>
  <div>
    <h1>Admin Panel</h1>
    <div v-if="!isAdmin">
      <p>Access Denied</p>
      <button @click="authenticate">Login</button>
    </div>
    <div v-else>
      <div>
        <h2>Test Subscription</h2>
        <input v-model="twitchId" placeholder="Enter Twitch ID" />
        <button @click="testSubscription">Test Subscription</button>
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
  </div>
</template>

<script>
import axios from "axios";

export default {
  data() {
    return {
      twitchId: "",
      response: null,
      isAdmin: false,
    };
  },
  methods: {
    async authenticate() {
      // Implement basic authentication (can be replaced with a more robust system)
      const password = prompt("Enter admin password:");
      if (password === "your_admin_password") {
        this.isAdmin = true;
      } else {
        alert("Incorrect password");
      }
    },
    async testSubscription() {
      try {
        const res = await axios.post(`/api/admin/test-subscription/${this.twitchId}`);
        this.response = res.data;
      } catch (error) {
        this.response = error.response.data;
      }
    },
    async deleteAllSubscriptions() {
      try {
        const res = await axios.delete("/api/admin/delete-all-subscriptions");
        this.response = res.data;
      } catch (error) {
        this.response = error.response.data;
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
  margin: 20px;
}
button {
  margin-top: 10px;
}
</style>
