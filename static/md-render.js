
MathJax.typeset([bodydiv]);
bodydiv.innerHTML = marked.parse(bodydiv.innerHTML);
bodydiv.style.display = 'inline';
