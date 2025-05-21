import { assets } from "$app/paths";

let menu = [
  {
    label: "File",
    icon: "fa-regular fa-folder-open",
    action: () => {
      console.log("File");
    },
  },
  {
    label: "Edit",
    icon: "fa-solid fa-pen",
    action: () => {
      console.log("Edit");
    },
  },
  {
    label: "View",
    icon: "fa-solid fa-eye",
    action: () => {
      console.log("View");
    },
  },
  {
    label: "Help",
    icon: "fa-solid fa-question",
    action: () => {
      console.log("Help");
    },
  },
];

let extraCmds = [
  {
    label: "",
    icon: "fa-regular fa-folder-open",
    action: () => {
      console.log("Extra command 1");
    },
  },
  {
    label: "",
    icon: "fa-solid fa-pen",
    action: () => {
      console.log("Extra command 2");
    },
  },
  {
    label: "",
    icon: "fa-solid fa-floppy-disk",
    action: () => {
      console.log("Extra command 3");
    },
  },
];

export const windowState = $state({
  title: "Window title test",
  menuIcon: `${assets}/icons/qi_64.png`,
  resizeable: true,
  draggable: true,
  showTitlebar: true,
  showStatusbar: true,
  showClose: true,
  showMinimize: true,
  showMaximize: true,
  edges: ["left", "right", "bottom", "top", "handle"],
  menuCommands: menu,
  extraCommands: extraCmds,
  status: "Status bar test",
  statusExtra: "Connected test ✔️",
});
