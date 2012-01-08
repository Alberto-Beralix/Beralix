<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<!--
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details.

You should have received a copy of the GNU Lesser General Public License
along with this program; see the file COPYING.LGPL.  If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
02111-1307, USA.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:exsl="http://exslt.org/common"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="exsl"
                version="1.0">

<!--!!==========================================================================
DocBook to HTML - CSS
:Requires: db2html-footnote db2html-callout db2html-qanda theme-colors theme-html

REMARK: Describe this module
-->


<xsl:template mode="html.css.mode" match="*">
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:text>
<!-- == common == -->
sub { font-size: 0.83em; }
sub sub { font-size: 1em; }
sup { font-size: 0.83em; }
sup sup { font-size: 1em; }
table.table-pgwide { width: 100%; }


td.td-colsep { border-</xsl:text><xsl:value-of select="$right"/><xsl:text>: solid 1px; }
td.td-rowsep { border-bottom: solid 1px; }
thead { border-top: solid 2px; border-bottom: solid 2px; }
tfoot { border-top: solid 2px; border-bottom: solid 2px; }

div.title span.label { font-weight: normal; }

div.sidenav {
  padding: 0.5em 1em 0 1em;
  background-color: </xsl:text><xsl:value-of select="$color.background"/><xsl:text>;
  border: solid 1px </xsl:text><xsl:value-of select="$color.gray_border"/><xsl:text>;
}
div.sidenav div.sectionlinks {
  background-color: </xsl:text><xsl:value-of select="$color.background"/><xsl:text>;
  border: none; padding: 0; margin: 0;
}
div.sidenav div.sectionlinks li { margin-bottom: 0.5em; }
div.sidenav div.sectionlinks div.sectionlinks div.sectionlinks {
  margin-top: 0;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1em;
  margin-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 0;
}
div.sidenav div.sectionlinks div.sectionlinks div.sectionlinks li { margin-bottom: 0; }

<!-- == bibliography == -->
span.bibliolabel {
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
span.citetitle {
  font-style: italic;
}

<!-- == block == -->
div.epigraph {
  text-align: </xsl:text><xsl:value-of select="$right"/><xsl:text>;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 20%;
  margin-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 0;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
div.programlisting .userinput {
  font-weight: bold;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
div.verbatim { white-space: pre; }


<!-- == unsorted == -->
dl.index dt { margin-top: 0; }
dl.index dd { margin-top: 0; margin-bottom: 0; }
dl.indexdiv dt { margin-top: 0; }
dl.indexdiv dd { margin-top: 0; margin-bottom: 0; }
dl.setindex dt { margin-top: 0; }
dl.setindex dd { margin-top: 0; margin-bottom: 0; }
div.simplelist { margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.72em; }
div.simplelist table { margin-left: 0; border: none; }
div.simplelist td {
  padding: 0.5em;
  border-</xsl:text><xsl:value-of select="$left"/><xsl:text>: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
<!--
div.simplelist td.td-first {
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 0;
  border-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 0;
}
-->

span.accel { text-decoration: underline; }
span.email { font-family: monospace; }
span.firstterm { font-style: italic; }
span.foreignphrase { font-style: italic; }

dt.glossterm span.glossterm { font-style: normal; }
<!--
dt.glossterm { margin-left: 0em; }
dd + dt.glossterm { margin-top: 2em; }
dd.glossdef, dd.glosssee, dd.glossseealso { margin-top: 0em;  margin-bottom: 0; }
-->

span.glossterm { font-style: italic; }

span.lineannotation { font-style: italic; }
span.medialabel { font-style: italic; }
.methodparam span.parameter { font-style: italic; }
span.paramdef span.parameter { font-style: italic; }
span.prompt { font-family: monospace; }
span.wordasword { font-style: italic; }
<!-- FIXME below -->

dt.question {
  margin-left: 0;
  margin-right: 0;
  font-weight: bold;
}
dd + dt.question { margin-top: 1em; }
dd.answer {
  margin-top: 1em;
  margin-left: 2em;
  margin-right: 2em;
}
div.qanda-label {
  line-height: 1.72em;
  float: </xsl:text><xsl:value-of select="$left"/><xsl:text>;
  margin-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 1em;
  font-weight: bold;
}
dl.qandaset ol, dl.qandaset ul, dl.qandaset table { clear: both; }

span.co {
  font-size: 0.83em;
  margin: 0 0.2em 0 0.2em;
  padding: 0 0.5em 0 0.5em;
  -moz-border-radius: 1em;
  -webkit-border-radius: 1em;
  border-radius: 1em;
  background-color: </xsl:text>
  <xsl:value-of select="$color.yellow_background"/><xsl:text>;
  border: solid 1px </xsl:text>
  <xsl:value-of select="$color.yellow_border"/><xsl:text>;
}
span.co a { text-decoration: none; }
span.co a:hover { text-decoration: none; }
div.co {
  margin: 0;
  float: </xsl:text><xsl:value-of select="$left"/><xsl:text>;
  clear: both;
}
</xsl:text>
<xsl:call-template name="db2html.footnote.css"/>
</xsl:template>

</xsl:stylesheet>
