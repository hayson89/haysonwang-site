import { FolderPage } from "@quartz-community/folder-page"

const displayTitles = {
  "medical_education/index": "健康科普",
}

export default function FolderPageTitles(options) {
  const folderPage = FolderPage(options)
  const generate = folderPage.generate

  return {
    ...folderPage,
    name: "FolderPageTitles",
    generate(context) {
      return generate(context).map((page) => ({
        ...page,
        title: displayTitles[page.slug] ?? page.title,
      }))
    },
  }
}
