<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:mal="http://www.gnome.org/~shaunm/mallard"
                xmlns:yelp="http://www.gnome.org/yelp/ns"
                xmlns="http://www.w3.org/1999/xhtml"
                extension-element-prefixes="yelp"
                version="1.0">

<xsl:import href="/usr/share/yelp-xsl/xslt/mallard/html/mal2xhtml.xsl"/>

<xsl:import href="yelp-common.xsl"/>

<xsl:param name="yelp.stub" select="false()"/>

<xsl:param name="mal2html.editor_mode" select="$yelp.editor_mode"/>

<xsl:param name="mal.if.supports.custom"
           select="'action:install'"/>

<xsl:param name="mal.cache" select="yelp:input()"/>

<!-- == mal.link.target == -->
<xsl:template name="mal.link.target">
  <xsl:param name="link" select="."/>
  <xsl:param name="action" select="$link/@action"/>
  <xsl:param name="xref" select="$link/@xref"/>
  <xsl:param name="href" select="$link/@href"/>
  <xsl:choose>
    <xsl:when test="starts-with($action, 'install:')">
      <xsl:value-of select="$action"/>
    </xsl:when>
    <xsl:when test="string($xref) = ''">
      <xsl:value-of select="$href"/>
    </xsl:when>
    <xsl:when test="contains($xref, '/')">
      <xsl:value-of select="$href"/>
    </xsl:when>
    <xsl:when test="contains($xref, '#')">
      <xsl:variable name="pageid" select="substring-before($xref, '#')"/>
      <xsl:variable name="sectionid" select="substring-after($xref, '#')"/>
      <xsl:value-of select="concat('xref:', $pageid, '#', $sectionid)"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="concat('xref:', $xref)"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template name="yelp.css.custom">
<xsl:text>
a.linkdiv:hover {
  outline: solid 1px </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
  background: -webkit-gradient(linear, left top, left 80, from(</xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>), to(</xsl:text>
    <xsl:value-of select="$color.background"/><xsl:text>));
}
</xsl:text>
<xsl:if test="$yelp.editor_mode">
<xsl:text>
div.version {
  margin: -1em -12px 1em -12px;
  padding: 0.5em 12px 0.5em 12px;
  position: relative;
  left: auto; right: auto;
  opacity: 1.0;
  max-width: none;
  border: none;
  border-bottom: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
}
div.version:hover { opacity: 1.0; }
</xsl:text>
<xsl:if test="$yelp.stub">
<xsl:text>
body, div.body {
  background-color: </xsl:text>
    <xsl:value-of select="$color.red_background"/><xsl:text>;
}
</xsl:text>
</xsl:if>
</xsl:if>
</xsl:template>

</xsl:stylesheet>
