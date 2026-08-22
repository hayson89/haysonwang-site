import { FolderPage } from "@quartz-community/folder-page"

const displayTitles = {
  "education/index": "健康教育",
  "research/index": "医学研究",
  "clinical/index": "临床实践",
  "nail-disease/index": "甲病专题",
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
