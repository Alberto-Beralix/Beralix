<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:yelp="http://www.gnome.org/yelp/ns"
                xmlns:set="http://exslt.org/sets"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="set"
                extension-element-prefixes="yelp"
                version="1.0">

<xsl:param name="yelp.editor_mode" select="false()"/>

<xsl:param name="html.extension" select="''"/>

<xsl:param name="html.syntax.highlight" select="true()"/>
<xsl:param name="html.js.root" select="'file:///usr/share/yelp-xsl/js/'"/>

<!-- == html.output == -->
<xsl:template name="html.output">
  <xsl:param name="node" select="."/>
  <xsl:param name="href">
    <xsl:choose>
      <xsl:when test="$node/@xml:id">
        <xsl:value-of select="$node/@xml:id"/>
      </xsl:when>
      <xsl:when test="$node/@id">
        <xsl:value-of select="$node/@id"/>
      </xsl:when>
      <xsl:when test="set:has-same-node($node, /*)">
        <xsl:value-of select="$html.basename"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="generate-id()"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:param>
  <yelp:document href="{$href}">
    <xsl:call-template name="html.page">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </yelp:document>
  <xsl:apply-templates mode="html.output.after.mode" select="$node"/>
</xsl:template>

<!-- == html.css.custom == -->
<xsl:template name="html.css.custom">
  <xsl:param name="direction"/>
  <xsl:param name="left"/>
  <xsl:param name="right"/>
<xsl:text>
html {
  height: 100%;
}
body {
  padding: 0;
  background-color: </xsl:text><xsl:value-of select="$color.background"/><xsl:text>;
  max-width: 100%;
}
div.header {
  max-width: 100%;
  width: 100%;
  padding: 0;
  margin: 0 0 1em 0;
}
div.code {
  -webkit-box-shadow: 0px 0px 4px </xsl:text><xsl:value-of select="$color.gray_border"/><xsl:text>;
}
div.code:hover {
  -webkit-box-shadow: 0px 0px 4px </xsl:text><xsl:value-of select="$color.blue_border"/><xsl:text>;
}
div.trails {
  margin: 0;
  padding: 0.2em 12px 0 12px;
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
  border-bottom: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
div.trail {
  font-size: 1em;
  margin: 0 1em 0.2em 1em;
  padding: 0;
}
a.trail { color:  </xsl:text>
  <xsl:value-of select="$color.text_light"/><xsl:text>; }
a.trail:hover { text-decoration: none; color:  </xsl:text>
  <xsl:value-of select="$color.link"/><xsl:text>; }
div.body {
  margin: 0 12px 0 12px;
  padding: 0 0 12px 0;
  border: none;
}
</xsl:text>
<xsl:call-template name="yelp.css.custom"/>
</xsl:template>

<xsl:template name="yelp.css.custom"/>

<!-- == html.js.custom == -->
<xsl:template name="html.js.custom">
<script type="text/javascript" language="javascript" src="/usr/share/yelp/js/jquery-ui-1.8.custom.min.js"/>
</xsl:template>

<!-- == html.js.content.custom == -->
<xsl:template name="html.js.content.custom">
<xsl:text>
$(document).ready (function () {
  if (location.hash != '') {
    $('#' + location.hash).find('div.hgroup').css({
      backgroundColor: '</xsl:text><xsl:value-of select="$color.yellow_background"/><xsl:text>'
    }).animate({
      backgroundColor: '</xsl:text><xsl:value-of select="$color.gray_background"/><xsl:text>'
    }, 8000);
    $('#' + location.hash).css({
      backgroundColor: '</xsl:text><xsl:value-of select="$color.yellow_background"/><xsl:text>'
    }).animate({
      backgroundColor: '</xsl:text><xsl:value-of select="$color.background"/><xsl:text>'
    }, 4000);
  }
});
</xsl:text>
</xsl:template>

</xsl:stylesheet>
