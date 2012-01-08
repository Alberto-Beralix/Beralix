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
                xmlns:mal="http://projectmallard.org/1.0/"
                xmlns:tt="http://www.w3.org/ns/ttml"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="mal tt"
                version="1.0">

<!--!!==========================================================================
Mallard to HTML - Media Elements

REMARK: Describe this module
-->

<!--**==========================================================================
mal2html.media.image
FIXME

FIXME
-->
<xsl:template name="mal2html.media.image">
  <xsl:param name="node" select="."/>
  <xsl:param name="inline" select="false()"/>
  <img src="{$node/@src}">
    <xsl:copy-of select="@height"/>
    <xsl:copy-of select="@width"/>
    <xsl:attribute name="alt">
      <xsl:choose>
        <xsl:when test="$inline">
          <xsl:value-of select="$node"/>
        </xsl:when>
        <xsl:otherwise>
          <!-- FIXME: This is not ideal.  Nested block container elements
               will introduce lots of garbage whitespace.  But then, XML
               processors are supposed to normalize whitespace in attribute
               values anyway.  Ideally, we'd have a set of modes for text
               conversion.  That'd probably be best handled in a set of
               mal2text stylesheets.
          -->
          <xsl:for-each select="$node/mal:*">
            <xsl:if test="position() &gt; 1">
              <xsl:text>&#x000A;</xsl:text>
            </xsl:if>
            <xsl:value-of select="string(.)"/>
          </xsl:for-each>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
  </img>
</xsl:template>

<!--**==========================================================================
mal2html.media.video
FIXME

FIXME
-->
<xsl:template name="mal2html.media.video">
  <xsl:param name="node" select="."/>
  <xsl:param name="inline" select="false()"/>
  <video src="{$node/@src}" autobuffer="autobuffer" controls="controls">
    <xsl:attribute name="class">
      <xsl:text>media </xsl:text>
      <xsl:choose>
        <xsl:when test="$inline">
          <xsl:text>media-inline</xsl:text>
        </xsl:when>
        <xsl:otherwise>
          <xsl:text>media-block</xsl:text>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
    <xsl:copy-of select="$node/@height"/>
    <xsl:copy-of select="$node/@width"/>
    <xsl:attribute name="data-play-label">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="'Play'"/>
      </xsl:call-template>
    </xsl:attribute>
    <xsl:attribute name="data-pause-label">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="'Pause'"/>
      </xsl:call-template>
    </xsl:attribute>
    <xsl:choose>
      <xsl:when test="$inline">
        <xsl:apply-templates mode="mal2html.inline.mode" select="$node/node()"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates mode="mal2html.block.mode" select="$node/node()"/>
      </xsl:otherwise>
    </xsl:choose>
  </video>
  <xsl:if test="not($inline)">
    <xsl:apply-templates mode="mal2html.ttml.mode" select="tt:tt"/>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
mal2html.media.audio
FIXME

FIXME
-->
<xsl:template name="mal2html.media.audio">
  <xsl:param name="node" select="."/>
  <xsl:param name="inline" select="false()"/>
  <audio src="{$node/@src}" autobuffer="autobuffer" controls="controls">
    <xsl:choose>
      <xsl:when test="$inline">
        <xsl:apply-templates mode="mal2html.inline.mode" select="$node/node()"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates mode="mal2html.block.mode" select="$node/node()"/>
      </xsl:otherwise>
    </xsl:choose>
  </audio>
</xsl:template>


<!-- == TTML == -->

<xsl:template mode="mal2html.block.mode" match="tt:*"/>

<xsl:template mode="mal2html.ttml.mode" match="tt:tt">
  <xsl:variable name="if">
    <xsl:call-template name="mal.if.test"/>
  </xsl:variable>
  <xsl:if test="$if = 'true'">
    <xsl:apply-templates mode="mal2html.ttml.mode" select="tt:body"/>
  </xsl:if>
</xsl:template>

<xsl:template mode="mal2html.ttml.mode" match="tt:body">
  <div class="media-ttml">
    <xsl:apply-templates mode="mal2html.ttml.mode" select="tt:div">
      <xsl:with-param name="range">
        <xsl:call-template name="mal2html.ttml.time.range"/>
      </xsl:with-param>
    </xsl:apply-templates>
  </div>
</xsl:template>

<xsl:template mode="mal2html.ttml.mode" match="tt:div">
  <xsl:param name="range"/>
  <xsl:apply-templates mode="mal2html.ttml.mode" select="tt:div | tt:p">
    <xsl:with-param name="range">
      <xsl:call-template name="mal2html.ttml.time.range">
        <xsl:with-param name="range" select="$range"/>
      </xsl:call-template>
    </xsl:with-param>
  </xsl:apply-templates>
</xsl:template>

<xsl:template mode="mal2html.ttml.mode" match="tt:p">
  <xsl:param name="range"/>
  <xsl:variable name="beginend">
    <xsl:call-template name="mal2html.ttml.time.range">
      <xsl:with-param name="range" select="$range"/>
    </xsl:call-template>
  </xsl:variable>
  <div class="media-ttml-node media-ttml-p">
    <xsl:attribute name="data-begin">
      <xsl:value-of select="substring-before($beginend, ',')"/>
    </xsl:attribute>
    <xsl:variable name="end" select="substring-after($beginend, ',')"/>
    <xsl:if test="$end != '∞'">
      <xsl:attribute name="data-end">
        <xsl:value-of select="$end"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:apply-templates mode="mal2html.inline.mode">
      <xsl:with-param name="range" select="$beginend"/>
    </xsl:apply-templates>
  </div>
</xsl:template>

<xsl:template mode="mal2html.inline.mode" match="tt:span">
  <xsl:param name="range"/>
  <xsl:variable name="beginend">
    <xsl:call-template name="mal2html.ttml.time.range">
      <xsl:with-param name="range" select="$range"/>
    </xsl:call-template>
  </xsl:variable>
  <span class="media-ttml-node media-ttml-span">
    <xsl:attribute name="data-begin">
      <xsl:value-of select="substring-before($beginend, ',')"/>
    </xsl:attribute>
    <xsl:attribute name="data-end">
      <xsl:value-of select="substring-after($beginend, ',')"/>
    </xsl:attribute>
    <xsl:apply-templates mode="mal2html.inline.mode"/>
  </span>
</xsl:template>

<xsl:template name="mal2html.ttml.time.range">
  <xsl:param name="range"/>
  <xsl:param name="begin" select="@begin"/>
  <xsl:param name="end" select="@end"/>
  <xsl:variable name="range_">
    <xsl:choose>
      <xsl:when test="$range != ''">
        <xsl:value-of select="$range"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:variable name="par" select="ancestor::tt:*[@begin][1]"/>
        <xsl:choose>
          <xsl:when test="$par">
            <xsl:for-each select="$par">
              <xsl:call-template name="mal2html.ttml.time.range"/>
            </xsl:for-each>
          </xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="'0,∞'"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:variable name="begin_s">
    <xsl:call-template name="mal2html.ttml.time.seconds">
      <xsl:with-param name="time" select="$begin"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:value-of select="number(substring-before($range_, ',')) + number($begin_s)"/>
  <xsl:text>,</xsl:text>
  <xsl:choose>
    <xsl:when test="$end">
      <xsl:variable name="end_s">
        <xsl:call-template name="mal2html.ttml.time.seconds">
          <xsl:with-param name="time" select="$end"/>
        </xsl:call-template>
      </xsl:variable>
      <xsl:variable name="end_ss" select="number(substring-before($range_, ',')) + number($end_s)"/>
      <xsl:choose>
        <xsl:when test="substring-after($range_, ',') = '∞'">
          <xsl:value-of select="$end_ss"/>
        </xsl:when>
        <xsl:when test="number(substring-after($range_, ',')) &lt; $end_ss">
          <xsl:value-of select="substring-after($range_, ',')"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="$end_ss"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="substring-after($range_, ',')"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template name="mal2html.ttml.time.seconds">
  <xsl:param name="time" select="0"/>
  <xsl:choose>
    <xsl:when test="substring($time, string-length($time) - 1) = 'ms'">
      <xsl:variable name="ms">
        <xsl:value-of select="substring($time, 1, string-length($time) - 2)"/>
      </xsl:variable>
      <xsl:value-of select="number($ms) div 1000"/>
    </xsl:when>
    <xsl:when test="substring($time, string-length($time)) = 's'">
      <xsl:value-of select="substring($time, 1, string-length($time) - 1)"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="0"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!-- == Matched Templates == -->

<!-- = mal2html.block.mode % media = -->
<xsl:template mode="mal2html.block.mode" match="mal:media">
  <xsl:variable name="if">
    <xsl:call-template name="mal.if.test"/>
  </xsl:variable>
  <xsl:variable name="style" select="concat(' ', @style, ' ')"/>
  <xsl:variable name="class">
    <xsl:choose>
      <xsl:when test="contains($style, ' floatstart ')">
        <xsl:text> floatstart</xsl:text>
      </xsl:when>
      <xsl:when test="contains($style, ' floatend ')">
        <xsl:text> floatend</xsl:text>
      </xsl:when>
      <xsl:when test="contains($style, ' floatleft ')">
        <xsl:text> floatleft</xsl:text>
      </xsl:when>
      <xsl:when test="contains($style, ' floatright ')">
        <xsl:text> floatright</xsl:text>
      </xsl:when>
    </xsl:choose>
  </xsl:variable>
  <xsl:choose>
    <xsl:when test="$if != 'true'"/>
    <xsl:when test="@type = 'image' or not(@type)">
      <div>
        <xsl:attribute name="class">
          <xsl:text>media media-image</xsl:text>
          <xsl:value-of select="$class"/>
        </xsl:attribute>
        <div class="inner">
          <xsl:call-template name="mal2html.media.image"/>
        </div>
      </div>
    </xsl:when>
    <xsl:when test="@type = 'video'">
      <div>
        <xsl:attribute name="class">
          <xsl:text>media media-video</xsl:text>
          <xsl:value-of select="$class"/>
        </xsl:attribute>
        <div class="inner">
          <xsl:call-template name="mal2html.media.video"/>
        </div>
      </div>
    </xsl:when>
    <xsl:when test="@type = 'audio'">
      <div>
        <xsl:attribute name="class">
          <xsl:text>media media-audio</xsl:text>
          <xsl:value-of select="$class"/>
        </xsl:attribute>
        <div class="inner">
          <xsl:call-template name="mal2html.media.audio"/>
        </div>
      </div>
    </xsl:when>
    <xsl:otherwise>
      <xsl:for-each select="mal:*">
        <xsl:apply-templates mode="mal2html.block.mode" select="."/>
      </xsl:for-each>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<!-- = mal2html.inline.mode % media = -->
<xsl:template mode="mal2html.inline.mode" match="mal:media">
  <xsl:choose>
    <xsl:when test="@action | @xref | @href">
      <a>
        <xsl:attribute name="href">
          <xsl:call-template name="mal.link.target"/>
        </xsl:attribute>
        <xsl:attribute name="title">
          <xsl:call-template name="mal.link.tooltip"/>
        </xsl:attribute>
        <xsl:apply-templates mode="mal2html.inline.content.mode" select="."/>
      </a>
    </xsl:when>
    <xsl:otherwise>
      <xsl:apply-templates mode="mal2html.inline.content.mode" select="."/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template mode="mal2html.inline.content.mode" match="mal:media">
  <xsl:choose>
    <xsl:when test="@type = 'image' or not(@type)">
      <span class="media media-image">
        <xsl:call-template name="mal2html.media.image">
          <xsl:with-param name="inline" select="true()"/>
        </xsl:call-template>
      </span>
    </xsl:when>
    <xsl:when test="@type = 'video'">
      <span class="media media-video">
        <xsl:call-template name="mal2html.media.video">
          <xsl:with-param name="inline" select="true()"/>
        </xsl:call-template>
      </span>
    </xsl:when>
    <xsl:when test="@type = 'audio'">
      <span class="media media-audio">
        <xsl:call-template name="mal2html.media.audio">
          <xsl:with-param name="inline" select="true()"/>
        </xsl:call-template>
      </span>
    </xsl:when>
    <xsl:otherwise>
      <xsl:apply-templates mode="mal2html.inline.mode"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

</xsl:stylesheet>
