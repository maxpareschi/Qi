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

export const windowSettings = $state({
  showTitlebar: true,

  icon: `${assets}/icons/qi_64.png`,
  //icon: "fa-solid fa-bars",
  appMenu: appMenu,
  title: "Window Title",
  fastAccessMenu: fastAccessMenu,

  showMinimize: true,
  showMaximize: true,
  showClose: true,

  showStatusbar: true,
  statusMessageMain: "Test Message Main",
  statusMessageSub: "Test Message Sub",

  resizable: true,
  draggable: true,
});
