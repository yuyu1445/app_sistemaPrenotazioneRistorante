const { createApp } = Vue;

const API_BASE = window.__API_BASE__ || "http://127.0.0.1:8000";
const DEFAULT_DURATION_MINUTES = Number(window.__BOOKING_DEFAULT_DURATION__ || 90);
const LUNCH_SLOTS = ["12:00", "12:30", "13:00", "13:30", "14:00"];
const DINNER_SLOTS = ["19:00", "19:30", "20:00", "20:30", "21:00", "21:30", "22:00"];
const MIN_GUESTS = 1;
const DEFAULT_MAX_GUESTS = 8;
const DEFAULT_GUEST_COUNT = 2;
const DEFAULT_TIME_START = "19:30";

const toMinutes = (value) => {
  if (!value) return 0;
  const [hours, minutes] = value.split(":");
  return Number(hours) * 60 + Number(minutes);
};

const addMinutes = (value, minutesToAdd) => {
  const total = toMinutes(value) + minutesToAdd;
  const hours = Math.floor(total / 60) % 24;
  const minutes = total % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
};

const trimTime = (value) => (value ? value.slice(0, 5) : "");
const todayIso = () => new Date().toISOString().slice(0, 10);

createApp({
  data() {
    return {
      // Screens: 'home', 'auth', 'app'
      currentScreen: "home",
      apiBase: API_BASE,
      activeView: "cliente",

      // Auth state
      authMode: "cliente", // 'cliente' or 'staff'
      authTab: "login", // 'login' or 'register'
      authToken: localStorage.getItem("authToken") || null,
      currentUser: JSON.parse(localStorage.getItem("currentUser") || "null"),
      authLoading: false,
      authMessage: "",

      // Login form
      loginUsername: "",
      loginPassword: "",

      // Register form
      registerName: "",
      registerPhone: "",
      registerEmail: "",
      registerUsername: "",
      registerPassword: "",

      // My bookings
      showMyBookings: false,
      myBookings: [],
      cancellingBookingId: null,

      // Tables and availability
      tables: [],
      customers: [],
      bookings: [],
      staffBookings: [],
      availabilityById: {},
      selectedDate: todayIso(),
      staffDate: todayIso(),
      timeStart: DEFAULT_TIME_START,
      lunchSlots: LUNCH_SLOTS,
      dinnerSlots: DINNER_SLOTS,
      guestCount: DEFAULT_GUEST_COUNT,
      minGuestCount: MIN_GUESTS,
      selectedTableId: null,
      onlyAvailable: true,
      autoRefresh: true,
      bookingMessage: "",
      bookingLoading: false,
      staffStatusFilter: "",
      staffMessage: "",
      pollTimer: null,
      loadingBookingIds: [],
    };
  },

  computed: {
    timeEnd() {
      return addMinutes(this.timeStart, DEFAULT_DURATION_MINUTES);
    },
    availabilityMap() {
      const map = {};
      const startMin = toMinutes(this.timeStart);
      const endMin = toMinutes(this.timeEnd);

      for (const table of this.tables) {
        const statusBlocked = ["occupied", "out_of_service"].includes(table.status);
        const capacityOk = table.capacity_max >= this.guestCount;
        const conflicts = this.bookings.some((booking) => {
          if (booking.status === "cancellata") return false;
          if (booking.table_id !== table.id) return false;
          const bookingStart = toMinutes(booking.time_start);
          const bookingEnd = toMinutes(booking.time_end);
          return bookingStart < endMin && bookingEnd > startMin;
        });

        const available = capacityOk && !statusBlocked && !conflicts;
        let label = "Disponibile";
        let badge = "available";
        if (!capacityOk) {
          label = "Capienza insufficiente";
          badge = "unavailable";
        } else if (statusBlocked) {
          label = "Non prenotabile";
          badge = "unavailable";
        } else if (conflicts) {
          label = "Occupato";
          badge = "unavailable";
        }

        map[table.id] = { available, selectable: available, label, badge };
      }
      if (Object.keys(this.availabilityById).length === 0) return map;
      return { ...map, ...this.availabilityById };
    },
    visibleTables() {
      if (!this.onlyAvailable) return this.tables;
      return this.tables.filter((table) => this.availabilityMap[table.id]?.available);
    },
    selectedTableLabel() {
      const table = this.tables.find((item) => item.id === this.selectedTableId);
      if (!table) return "Nessun tavolo selezionato";
      return `Tavolo ${table.table_number} (capienza ${table.capacity_max})`;
    },
    totalTables() {
      return this.tables.length;
    },
    availableCount() {
      return this.tables.filter((table) => this.availabilityMap[table.id]?.available).length;
    },
    busyCount() {
      return this.tables.filter((table) => !this.availabilityMap[table.id]?.available).length;
    },
    maxGuestCount() {
      const maxCapacity = this.tables.reduce((max, table) => Math.max(max, table.capacity_max || 0), 0);
      return Math.max(this.minGuestCount, maxCapacity > 0 ? maxCapacity : DEFAULT_MAX_GUESTS);
    },
    staffBookingsEnriched() {
      const customerMap = new Map(this.customers.map((c) => [c.id, c]));
      const tableMap = new Map(this.tables.map((t) => [t.id, t]));
      return this.staffBookings.map((booking) => {
        const customer = customerMap.get(booking.customer_id);
        const table = tableMap.get(booking.table_id);
        return {
          ...booking,
          customer_name: customer ? customer.full_name : "Cliente sconosciuto",
          customer_phone: customer ? customer.phone : "",
          customer_email: customer ? customer.email : "",
          table_number: table ? table.table_number : "-",
        };
      });
    },
    staffBookingsFiltered() {
      if (!this.staffStatusFilter) return this.staffBookingsEnriched;
      return this.staffBookingsEnriched.filter((booking) => booking.status === this.staffStatusFilter);
    },
    staffStats() {
      return this.staffBookingsEnriched.reduce(
        (acc, booking) => {
          if (booking.status === "in attesa") acc.pending += 1;
          if (booking.status === "confermata") acc.confirmed += 1;
          return acc;
        },
        { pending: 0, confirmed: 0 }
      );
    },
  },

  methods: {
    // === AUTH METHODS ===
    showAuthScreen(mode) {
      this.authMode = mode;
      this.authTab = "login";
      this.authMessage = "";
      this.resetAuthForms();
      this.currentScreen = "auth";
    },
    setAuthTab(tab) {
      this.authTab = tab;
      this.authMessage = "";
      this.resetAuthForms();
    },
    resetAuthForms() {
      this.loginUsername = "";
      this.loginPassword = "";
      this.registerName = "";
      this.registerPhone = "";
      this.registerEmail = "";
      this.registerUsername = "";
      this.registerPassword = "";
    },

    async loginCustomer() {
      await this.doLogin("customer");
    },

    async loginStaff() {
      await this.doLogin("staff");
    },

    async doLogin(expectedType) {
      this.authLoading = true;
      this.authMessage = "";

      try {
        const response = await fetch(`${this.apiBase}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: this.loginUsername,
            password: this.loginPassword,
          }),
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || "Credenziali non valide");
        }

        const data = await response.json();

        if (expectedType === "staff" && data.user_type !== "staff") {
          throw new Error("Credenziali non valide per lo staff");
        }
        if (expectedType === "customer" && data.user_type !== "customer") {
          throw new Error("Credenziali non valide per i clienti");
        }

        this.authToken = data.access_token;
        this.currentUser = { ...data.user, user_type: data.user_type };
        localStorage.setItem("authToken", data.access_token);
        localStorage.setItem("currentUser", JSON.stringify(this.currentUser));

        this.activeView = data.user_type === "staff" ? "staff" : "cliente";
        this.resetAuthForms();
        this.currentScreen = "app";
        await this.refreshAll();
        this.startPolling();
      } catch (error) {
        this.authMessage = error.message;
      } finally {
        this.authLoading = false;
        this.resetAuthForms();
      }
    },

    async registerCustomer() {
      this.authLoading = true;
      this.authMessage = "";

      try {
        const response = await fetch(`${this.apiBase}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: this.registerName,
            phone: this.registerPhone,
            email: this.registerEmail,
            username: this.registerUsername,
            password: this.registerPassword,
          }),
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || "Errore durante la registrazione");
        }

        const data = await response.json();
        this.authToken = data.access_token;
        this.currentUser = { ...data.user, user_type: data.user_type };
        localStorage.setItem("authToken", data.access_token);
        localStorage.setItem("currentUser", JSON.stringify(this.currentUser));

        this.activeView = "cliente";
        this.resetAuthForms();
        this.currentScreen = "app";
        await this.refreshAll();
        this.startPolling();
      } catch (error) {
        this.authMessage = error.message;
      } finally {
        this.authLoading = false;
        this.resetAuthForms();
      }
    },

    logout() {
      this.authToken = null;
      this.currentUser = null;
      localStorage.removeItem("authToken");
      localStorage.removeItem("currentUser");
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
      this.goHome();
    },

    goHome() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
      this.currentScreen = "home";
      this.bookingMessage = "";
      this.staffMessage = "";
      this.authMessage = "";
      this.resetAuthForms();
      this.showMyBookings = false;
      this.resetSelection();
    },

    // === MY BOOKINGS ===
    toggleMyBookings() {
      this.showMyBookings = !this.showMyBookings;
      if (this.showMyBookings) {
        this.fetchMyBookings();
      }
    },

    async fetchMyBookings() {
      if (!this.authToken) return;

      try {
        const response = await fetch(`${this.apiBase}/my-bookings`, {
          headers: { Authorization: `Bearer ${this.authToken}` },
        });

        if (!response.ok) throw new Error("Errore nel caricamento delle prenotazioni");

        this.myBookings = await response.json();
      } catch (error) {
        console.error("Error fetching my bookings:", error);
      }
    },

    async cancelMyBooking(bookingId) {
      if (!this.authToken) return;

      this.cancellingBookingId = bookingId;

      try {
        const response = await fetch(`${this.apiBase}/my-bookings/${bookingId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${this.authToken}` },
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || "Errore nella cancellazione");
        }

        await this.fetchMyBookings();
        await this.refreshBookings();
      } catch (error) {
        alert(error.message);
      } finally {
        this.cancellingBookingId = null;
      }
    },

    formatDate(dateStr) {
      const date = new Date(dateStr);
      return date.toLocaleDateString("it-IT", {
        weekday: "long",
        day: "numeric",
        month: "long",
      });
    },

    // === BOOKING METHODS ===
    async createBookingAsCustomer() {
      if (!this.currentUser || !this.authToken) {
        this.bookingMessage = "Devi effettuare l'accesso per prenotare.";
        return;
      }

      if (!this.selectedTableId) {
        this.bookingMessage = "Seleziona un tavolo disponibile.";
        return;
      }

      this.bookingLoading = true;
      this.bookingMessage = "";

      try {
        const response = await fetch(`${this.apiBase}/bookings`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.authToken}`,
          },
          body: JSON.stringify({
            customer_id: this.currentUser.id,
            table_id: this.selectedTableId,
            reservation_date: this.selectedDate,
            time_start: this.timeStart,
            time_end: this.timeEnd,
            guest_count: this.guestCount,
          }),
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || "Errore nella prenotazione");
        }

        this.bookingMessage = "Prenotazione inviata con successo!";
        this.selectedTableId = null;
        await this.refreshBookings();
        await this.fetchMyBookings();
      } catch (error) {
        this.bookingMessage = error.message;
      } finally {
        this.bookingLoading = false;
      }
    },

    // === EXISTING METHODS ===
    statusLabel(status) {
      const map = {
        available: "Disponibile",
        occupied: "Occupato",
        reserved: "Riservato",
        out_of_service: "Fuori servizio",
      };
      return map[status] || status;
    },

    statusBadge(status) {
      if (status === "confermata" || status === "completata") return "available";
      if (status === "cancellata") return "unavailable";
      return "warning";
    },

    tableCardClass(table) {
      const availability = this.availabilityMap[table.id];
      return {
        selected: table.id === this.selectedTableId,
        unavailable: !availability?.available,
      };
    },

    async fetchJson(path, options = {}) {
      const headers = { ...options.headers };
      if (this.authToken) {
        headers.Authorization = `Bearer ${this.authToken}`;
      }

      const response = await fetch(`${this.apiBase}${path}`, { ...options, headers });
      if (!response.ok) {
        let errorMessage = response.statusText;
        try {
          const data = await response.json();
          if (data.detail) errorMessage = data.detail;
        } catch (err) {}
        throw new Error(errorMessage);
      }
      return await response.json();
    },

    async refreshCore() {
      const [tables, customers] = await Promise.all([
        this.fetchJson("/tables"),
        this.fetchJson("/customers"),
      ]);
      this.tables = tables;
      this.customers = customers;
    },

    async refreshTables() {
      this.tables = await this.fetchJson("/tables");
    },

    async refreshBookings() {
      const data = await this.fetchJson(
        `/bookings?reservation_date=${this.selectedDate}&limit=200&offset=0`
      );
      this.bookings = data.map((booking) => ({
        ...booking,
        time_start: trimTime(booking.time_start),
        time_end: trimTime(booking.time_end),
      }));
    },

    async refreshStaffBookings() {
      const data = await this.fetchJson(
        `/bookings?reservation_date=${this.staffDate}&limit=200&offset=0`
      );
      this.staffBookings = data.map((booking) => ({
        ...booking,
        time_start: trimTime(booking.time_start),
        time_end: trimTime(booking.time_end),
      }));
    },

    async refreshAll() {
      try {
        await this.refreshCore();
        await this.refreshBookings();
        await this.refreshStaffBookings();
        await this.refreshAvailability();
        if (this.activeView === "cliente" && this.showMyBookings) {
          await this.fetchMyBookings();
        }
      } catch (error) {
        this.bookingMessage = `Errore di connessione: ${error.message}`;
      }
    },

    async refreshAvailability() {
      if (this.currentScreen !== "app") return;
      const params = new URLSearchParams({
        reservation_date: this.selectedDate,
        time_start: this.timeStart,
        time_end: this.timeEnd,
        guest_count: String(this.guestCount),
      });
      try {
        const data = await this.fetchJson(`/availability?${params.toString()}`);
        this.availabilityById = data.reduce((acc, entry) => {
          acc[entry.id] = {
            available: entry.available,
            selectable: entry.selectable,
            label: entry.label,
            badge: entry.badge,
          };
          return acc;
        }, {});
      } catch (error) {
        this.availabilityById = {};
      }
    },

    selectTable(table) {
      if (!this.availabilityMap[table.id]?.selectable) return;
      this.selectedTableId = table.id;
      this.bookingMessage = "";
    },

    resetSelection() {
      this.selectedTableId = null;
      this.bookingMessage = "";
    },
    resetBookingForm() {
      this.selectedDate = todayIso();
      this.timeStart = DEFAULT_TIME_START;
      const defaultGuests = Math.min(
        this.maxGuestCount,
        Math.max(this.minGuestCount, DEFAULT_GUEST_COUNT)
      );
      this.guestCount = defaultGuests;
      this.selectedTableId = null;
      this.bookingMessage = "";
    },

    isBookingActionLoading(bookingId) {
      return this.loadingBookingIds.includes(bookingId);
    },

    async updateBookingStatus(booking, status) {
      if (this.isBookingActionLoading(booking.id)) return;
      this.staffMessage = "";
      this.loadingBookingIds = [...this.loadingBookingIds, booking.id];

      try {
        const response = await fetch(`${this.apiBase}/bookings/${booking.id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.authToken}`,
          },
          body: JSON.stringify({ status }),
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || "Errore aggiornando la prenotazione");
        }

        await this.refreshStaffBookings();
        await this.refreshBookings();
      } catch (error) {
        this.staffMessage = error.message;
      } finally {
        this.loadingBookingIds = this.loadingBookingIds.filter((id) => id !== booking.id);
      }
    },

    async cancelBooking(booking) {
      if (this.isBookingActionLoading(booking.id)) return;
      if (!window.confirm("Vuoi cancellare questa prenotazione?")) return;

      this.staffMessage = "";
      this.loadingBookingIds = [...this.loadingBookingIds, booking.id];

      try {
        const response = await fetch(`${this.apiBase}/bookings/${booking.id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${this.authToken}` },
        });

        if (!response.ok && response.status !== 204) {
          const data = await response.json();
          throw new Error(data.detail || "Errore cancellando la prenotazione");
        }

        await this.refreshStaffBookings();
        await this.refreshBookings();
      } catch (error) {
        this.staffMessage = error.message;
      } finally {
        this.loadingBookingIds = this.loadingBookingIds.filter((id) => id !== booking.id);
      }
    },

    startPolling() {
      if (this.pollTimer) clearInterval(this.pollTimer);
      if (this.currentScreen !== "app") return;
      this.pollTimer = setInterval(() => {
        if (!this.autoRefresh) return;
        if (this.activeView === "cliente") {
          this.refreshTables();
          this.refreshAvailability();
        } else {
          this.refreshTables();
          this.refreshStaffBookings();
        }
      }, 15000);
    },
  },

  watch: {
    selectedDate() {
      this.refreshBookings();
      this.refreshAvailability();
    },
    staffDate() {
      this.refreshStaffBookings();
    },
    activeView() {
      this.startPolling();
    },
    autoRefresh() {
      this.startPolling();
    },
    timeStart() {
      this.resetSelection();
      this.refreshAvailability();
    },
    guestCount() {
      const value = Number(this.guestCount);
      if (Number.isNaN(value)) {
        this.guestCount = this.minGuestCount;
        return;
      }
      if (value < this.minGuestCount) {
        this.guestCount = this.minGuestCount;
        return;
      }
      if (value > this.maxGuestCount) {
        this.guestCount = this.maxGuestCount;
        return;
      }
      this.resetSelection();
      this.refreshAvailability();
    },
    maxGuestCount(newValue) {
      if (this.guestCount > newValue) {
        this.guestCount = newValue;
      }
    },
  },

  mounted() {
    this.currentScreen = "home";
    this.resetAuthForms();
  },
}).mount("#app");
