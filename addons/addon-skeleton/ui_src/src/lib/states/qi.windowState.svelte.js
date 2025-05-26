import { assets } from "$app/paths";

const appMenu = [
  {
    label: "File",
    icon: "",
    action: () => {
      console.log("File");
    },
  },
  {
    label: "Edit",
    icon: "",
    action: () => {
      console.log("Edit");
    },
  },
  {
    label: "View",
    icon: "",
    action: () => {
      console.log("View");
    },
  },
  {
    label: "Help",
    icon: "",
    action: () => {
      console.log("Help");
    },
  },
];

const fastAccessMenu = [
  {
    label: "",
    icon: "fa-solid fa-plus",
    action: () => {
      console.log("New File");
    },
  },
  {
    label: "",
    icon: "fa-solid fa-pen",
    action: () => {
      console.log("Edit File");
    },
  },
  {
    label: "",
    icon: "fa-solid fa-trash",
    action: () => {
      console.log("Delete File");
    },
  },
  {
    label: "",
    icon: "fa-solid fa-eye",
    action: () => {
      console.log("View File");
    },
  },
  {
    label: "",
    icon: "fa-solid fa-gear",
    action: () => {
      console.log("Settings");
    },
  },
];

export let windowFlags = $state({
  resizeable: true,
  resizeSides: [
    "top",
    "bottom",
    "left",
    "right",
    "bottom-right",
    "bottom-left",
  ],
  draggable: true,
  showTitlebar: true,
  appMenuOpenedAtStart: false,
  showMinimize: true,
  showMaximize: true,
  showClose: true,
  showStatusbar: true,
  showAppBorder: true,
});

export let windowState = $state({
  isMoving: false,
  isResizing: false,
  isMaximized: false,
  resizingSide: null,
  dpi: window.devicePixelRatio,
  mousePosition: { x: 0, y: 0 },
  windowSize: { width: 0, height: 0 },
  windowPosition: { x: 0, y: 0 },
  minSize: { width: 400, height: 300 },

  title: "Window Title",
  icon: `${assets}/icons/qi_64.png`, // or icon: "fa-solid fa-bars"

  appMenu: appMenu,
  fastAccessMenu: fastAccessMenu,

  statusMessageMain: "Test Message Main",
  statusMessageSub: "Test Message Sub",
});
