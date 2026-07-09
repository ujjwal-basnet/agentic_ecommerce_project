#let slide-background = rgb("#FAF6EE")
#let primary-color = rgb("#1E293B")
#let secondary-color = rgb("#3B82F6")
#let text-color = rgb("#0F172A")
#let gray-color = rgb("#64748B")

#let slide-layout(title: "", section: "", body) = {
  set page(
    paper: "presentation-16-9",
    margin: (x: 2cm, y: 1.8cm),
    fill: slide-background,
    header: context {
      let page-num = counter(page).get().first()
      if page-num > 1 {
        grid(
          columns: (1fr, auto),
          align(left)[
            #text(size: 10pt, fill: gray-color, weight: "bold")[#upper(section)]
          ],
          align(right)[
            #text(size: 10pt, fill: gray-color)[SmartShop API Core Architecture]
          ]
        )
        v(-0.5em)
        line(length: 100%, stroke: 0.5pt + gray-color)
      }
    },
    footer: context {
      let page-num = counter(page).get().first()
      if page-num > 1 {
        line(length: 100%, stroke: 0.5pt + gray-color)
        v(0.2em)
        grid(
          columns: (1fr, auto),
          align(left)[
            #text(size: 8pt, fill: gray-color)[Confidential -- researchcontentlab\@gmail.com]
          ],
          align(right)[
            #text(size: 8pt, fill: gray-color)[Slide #page-num]
          ]
        )
      }
    }
  )

  set text(
    font: "Liberation Sans",
    size: 18pt,
    fill: text-color,
  )

  set par(leading: 0.7em)

  if title != "" {
    block(width: 100%, below: 1.5em)[
      #text(size: 28pt, weight: "bold", fill: primary-color)[#title]
      #v(-0.2em)
      #line(length: 30%, stroke: 3pt + secondary-color)
    ]
  }

  body
}

#let title-slide(title: "", subtitle: "", author: "", project: "") = {
  set page(
    paper: "presentation-16-9",
    margin: (x: 2cm, y: 2cm),
    fill: primary-color,
  )
  set text(
    font: "Liberation Sans",
    fill: rgb("#FFFFFF"),
    size: 20pt,
  )

  align(center + horizon)[
    #text(size: 36pt, weight: "bold", fill: rgb("#FFFFFF"))[#title]
    #v(0.5em)
    #text(size: 20pt, fill: rgb("#94A3B8"))[#subtitle]
    
    #v(2.5em)
    #line(length: 40%, stroke: 1.5pt + secondary-color)
    #v(1em)
    #text(size: 14pt, fill: rgb("#CBD5E1"))[#author]
    #v(0.5em)
    #text(size: 12pt, fill: rgb("#94A3B8"))[Project ID: #project]
  ]
}

#let divider-slide(title: "") = {
  set page(
    paper: "presentation-16-9",
    margin: (x: 2cm, y: 2cm),
    fill: secondary-color,
  )
  set text(
    font: "Liberation Sans",
    fill: rgb("#FFFFFF"),
    size: 24pt,
  )

  align(center + horizon)[
    #rect(fill: primary-color, inset: 1.5em, radius: 10pt)[
      #text(size: 32pt, weight: "bold", fill: rgb("#FFFFFF"))[#title]
    ]
  ]
}
