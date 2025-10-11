const { createApp } = Vue;

const appRoot = document.getElementById("app");
const uploadStatementEndpoint = appRoot?.dataset.uploadUrl || "/";

createApp({
  data() {
    return {
      sourceName: "",
      file: null,
      isSubmitting: false,
      message: "",
      messageType: "success",
      result: null,
    };
  },
  computed: {
    csrfToken() {
      const match = document.cookie.match(/csrftoken=([^;]+)/);
      return match ? decodeURIComponent(match[1]) : "";
    },
    statementSummary() {
      if (!this.result) {
        return "";
      }

      const statementId = this.result.statement_id;
      const fileName = this.result.file_name || "";

      const idText = statementId ? `#${statementId}` : "";
      return [idText, fileName].filter(Boolean).join(" · ");
    },
    transactionsCreated() {
      if (!this.result) {
        return "";
      }

      const { transactions_created: transactionsCreated } = this.result;
      return typeof transactionsCreated === "number"
        ? transactionsCreated
        : transactionsCreated || "";
    },
  },
  methods: {
    onFileChange(event) {
      const [file] = event.target.files;
      this.file = file || null;
      this.result = null;
      this.message = "";
    },
    async submitForm() {
      if (!this.file) {
        this.message = "Selecciona un archivo CSV antes de continuar.";
        this.messageType = "error";
        return;
      }

      this.isSubmitting = true;
      this.message = "";
      this.messageType = "success";

      const formData = new FormData();
      formData.append("source_name", this.sourceName.trim());
      formData.append("file", this.file);

      try {
        const response = await fetch(uploadStatementEndpoint, {
          method: "POST",
          headers: {
            "X-CSRFToken": this.csrfToken,
          },
          body: formData,
        });

        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload.error || "No se ha podido completar la importación.");
        }

        this.result = payload;
        const ignored = Number(payload.transactions_ignored || 0);
        if (ignored > 0) {
          const plural = ignored === 1 ? "entrada duplicada" : "entradas duplicadas";
          const verb = ignored === 1 ? "ha" : "han";
          this.message = `Importación realizada correctamente. Se ${verb} ignorado ${ignored} ${plural}.`;
        } else {
          this.message = "Importación realizada correctamente.";
        }
        this.messageType = "success";
        this.sourceName = "";
        this.file = null;
        this.$refs.fileInput.value = "";
      } catch (error) {
        this.message = error.message;
        this.messageType = "error";
      } finally {
        this.isSubmitting = false;
      }
    },
  },
  mounted() {
    if (!this.sourceName) {
      this.sourceName = "Importación manual";
    }
  },
}).mount("#app");
