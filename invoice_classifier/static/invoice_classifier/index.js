const { createApp } = Vue;

createApp({
  delimiters: ["[[", "]]"],
  data() {
    return {
      invoiceText: "",
      classification: null,
      loading: false,
      error: null,
      endpoint: window.invoiceClassifierEndpoint || "/api/invoice-classifier/",
    };
  },
  computed: {
    formattedClassification() {
      if (!this.classification) {
        return "";
      }

      if (typeof this.classification === "string") {
        return this.classification;
      }

      try {
        return JSON.stringify(this.classification, null, 2);
      } catch (error) {
        console.warn("Unable to format classification payload", error);
        return String(this.classification);
      }
    },
  },
  methods: {
    async classifyInvoice() {
      const payload = this.invoiceText.trim();

      if (!payload) {
        this.error = "Please enter invoice text before classifying.";
        this.classification = null;
        return;
      }

      this.loading = true;
      this.error = null;
      this.classification = null;

      try {
        const response = await fetch(this.endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ invoice_text: payload }),
        });

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        const data = await response.json();
        this.classification = data;
      } catch (error) {
        this.error = error.message || "An unexpected error occurred.";
      } finally {
        this.loading = false;
      }
    },
    resetForm() {
      this.invoiceText = "";
      this.classification = null;
      this.error = null;
    },
  },
}).mount("#invoice-classifier-app");
