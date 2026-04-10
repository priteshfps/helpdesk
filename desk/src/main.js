import { createApp, h } from "vue";
import {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  frappeRequest,
  FrappeUI,
  Input,
  setConfig,
  TextInput,
  toast,
  Tooltip,
} from "frappe-ui";
import { createPinia } from "pinia";
import App from "./App.vue";
import { createDialog } from "./components/dialogs";
import "./index.css";
import { restoreHDTheme, setHDTheme } from "./utils/themeColor";
import { router } from "./router";
import { telemetryPlugin } from "frappe-ui/frappe";
import { isCustomerPortal } from "@/utils";
import { translationPlugin } from "./translation";
import CircleAlert from "~icons/lucide/circle-alert";
import { initSocket } from "./socket";

const globalComponents = {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  Input,
  Tooltip,
  TextInput,
};

// Single root class — all theme CSS is scoped under body.hd-app
document.body.classList.add("hd-app");

// Restore saved theme (or keep default violet from index.css)
restoreHDTheme();
// Expose globally so agents/admins can retheme from the browser console:
//   window.setHDTheme('#0ea5e9')
window.setHDTheme = setHDTheme;

setConfig("resourceFetcher", frappeRequest);
setConfig("serverMessagesHandler", (msgs) => {
  if (isCustomerPortal.value) {
    return;
  }
  msgs.forEach((msg) => {
    msg = JSON.parse(msg);
    if (msg && msg.message == "Feedback email has been sent to the customer") {
      toast.success(msg.message);
      return;
    }
    toast.create({
      message: msg.message,
      icon: h(CircleAlert, { class: "text-blue-500" }),
    });
  });
});
setConfig("fallbackErrorHandler", (error) => {
  const msg = error.exc_type
    ? (error.messages || error.message || []).join(", ")
    : error.message;
  toast.error(msg);
});

const pinia = createPinia();
const app = createApp(App);

app.use(FrappeUI);
app.use(pinia);
app.use(router);
app.use(translationPlugin);
app.use(telemetryPlugin, { app_name: "helpdesk" });

for (const c in globalComponents) {
  app.component(c, globalComponents[c]);
}

app.config.globalProperties.$dialog = createDialog;

let socket;
if (import.meta.env.DEV) {
  frappeRequest({
    url: "/api/method/helpdesk.www.helpdesk.index.get_context_for_dev",
  }).then((values) => {
    for (let key in values) {
      window[key] = values[key];
    }
    socket = initSocket();
    app.config.globalProperties.$socket = socket;
    app.mount("#app");
  });
} else {
  socket = initSocket();
  app.config.globalProperties.$socket = socket;
  app.mount("#app");
}
