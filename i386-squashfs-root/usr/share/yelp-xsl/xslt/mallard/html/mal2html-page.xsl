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
                xmlns:ui="http://projectmallard.org/experimental/ui/"
                xmlns:e="http://projectmallard.org/experimental/"
                xmlns:exsl="http://exslt.org/common"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="mal ui e exsl"
                version="1.0">

<!--!!==========================================================================
Mallard to HTML - Pages

REMARK: Describe this module
-->


<!--@@==========================================================================
mal2html.editor_mode
Add information that's useful to writers and editors.

When this parameter is set to true, these stylesheets will output editorial
comments, status markers, and other information that's useful to writers and
editors.
-->
<xsl:param name="mal2html.editor_mode" select="false()"/>


<!--**==========================================================================
mal2html.page.copyrights
Output the copyright notice at the bottom of a page.
:Revision:version="1.0" date="2010-01-02"
$node: The top-level #{page} element.

This template outputs copyright information.  By default, it is placed at the
bottom of the page by *{mal2html.page.footbar}.  Copyrights are taken from the
#{credit} elements in the #{info} element in ${node}.

Copyright information is output in a #{div} element with #{class="copyrights"}.
Each copyright is output in a nested #{div} element with #{class="copyright"}.
-->
<xsl:template name="mal2html.page.copyrights">
  <xsl:param name="node" select="."/>
  <div class="copyrights">
    <xsl:for-each select="$node/mal:info/mal:credit[mal:years]">
      <div class="copyright">
        <!-- FIXME: i18n, multi-year, email -->
        <xsl:value-of select="concat('© ', mal:years, ' ', mal:name)"/>
      </div>
    </xsl:for-each>
  </div>
</xsl:template>


<!--**==========================================================================
mal2html.page.linktrails
FIXME

REMARK: Describe this template
-->
<xsl:template name="mal2html.page.linktrails">
  <xsl:param name="node" select="."/>
  <xsl:variable name="linktrails">
    <xsl:call-template name="mal.link.linktrails">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:variable name="trailnodes" select="exsl:node-set($linktrails)/*"/>
  <xsl:if test="count($trailnodes) &gt; 0">
    <div class="trails">
      <xsl:for-each select="$trailnodes">
        <xsl:sort select="(.//mal:title[@type='sort'])[1]"/>
        <xsl:sort select="(.//mal:title[@type='sort'])[2]"/>
        <xsl:sort select="(.//mal:title[@type='sort'])[3]"/>
        <xsl:sort select="(.//mal:title[@type='sort'])[4]"/>
        <xsl:sort select="(.//mal:title[@type='sort'])[5]"/>
        <xsl:call-template name="mal2html.page.linktrails.trail"/>
      </xsl:for-each>
    </div>
  </xsl:if>
</xsl:template>

<!--**==========================================================================
mal2html.page.linktrails.trail
FIXME

REMARK: Describe this template
-->
<xsl:template name="mal2html.page.linktrails.trail">
  <xsl:param name="node" select="."/>
  <div class="trail">
    <xsl:call-template name="mal2html.page.linktrails.link">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </div>
</xsl:template>

<!--**==========================================================================
mal2html.page.linktrails.link
FIXME

REMARK: Describe this template
-->
<xsl:template name="mal2html.page.linktrails.link">
  <xsl:param name="node" select="."/>
  <a class="trail">
    <xsl:attribute name="href">
      <xsl:call-template name="mal.link.target">
        <xsl:with-param name="xref" select="$node/@xref"/>
      </xsl:call-template>
    </xsl:attribute>
    <xsl:attribute name="title">
      <xsl:call-template name="mal.link.tooltip">
        <xsl:with-param name="xref" select="$node/@xref"/>
      </xsl:call-template>
    </xsl:attribute>
    <xsl:call-template name="mal.link.content">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="xref" select="$node/@xref"/>
      <xsl:with-param name="role" select="'trail'"/>
    </xsl:call-template>
  </a>
  <xsl:variable name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:variable>
  <xsl:choose>
    <xsl:when test="$direction = 'rtl'">
      <xsl:choose>
        <xsl:when test="$node/@child = 'section'">
          <xsl:text>&#x00A0;‹ </xsl:text>
        </xsl:when>
        <xsl:otherwise>
          <xsl:text>&#x00A0;« </xsl:text>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:when>
    <xsl:otherwise>
      <xsl:choose>
        <xsl:when test="$node/@child = 'section'">
          <xsl:text>&#x00A0;› </xsl:text>
        </xsl:when>
        <xsl:otherwise>
          <xsl:text>&#x00A0;» </xsl:text>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:otherwise>
  </xsl:choose>
  <xsl:for-each select="$node/mal:link">
    <xsl:call-template name="mal2html.page.linktrails.link"/>
  </xsl:for-each>
</xsl:template>

<xsl:template name="mal2html.editor.badge">
  <xsl:param name="target" select="."/>
  <xsl:if test="$mal2html.editor_mode">
    <xsl:variable name="page" select="$target/ancestor-or-self::mal:page[1]"/>
    <xsl:variable name="date">
      <xsl:for-each select="$page/mal:info/mal:revision">
        <xsl:sort select="@date" data-type="text" order="descending"/>
        <xsl:if test="position() = 1">
          <xsl:value-of select="@date"/>
        </xsl:if>
      </xsl:for-each>
    </xsl:variable>
    <xsl:variable name="revision"
                  select="$page/mal:info/mal:revision[@date = $date][last()]"/>
    <xsl:if test="$revision/@status != '' and $revision/@status != 'final'">
      <xsl:text> </xsl:text>
      <span>
        <xsl:attribute name="class">
          <xsl:value-of select="concat('status status-', $revision/@status)"/>
        </xsl:attribute>
        <!-- FIXME: i18n -->
        <xsl:choose>
          <xsl:when test="$revision/@status = 'stub'">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Stub'"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:when test="$revision/@status = 'incomplete'">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Incomplete'"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:when test="$revision/@status = 'draft'">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Draft'"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:when test="$revision/@status = 'outdated'">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Outdated'"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:when test="$revision/@status = 'review'">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Ready for review'"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:when test="$revision/@status = 'candidate'">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Candidate'"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:when test="$revision/@status = 'final'">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Final'"/>
            </xsl:call-template>
          </xsl:when>
        </xsl:choose>
      </span>
    </xsl:if>
  </xsl:if>
</xsl:template>

<xsl:template name="mal2html.editor.banner">
  <xsl:param name="node" select="."/>
  <xsl:if test="$mal2html.editor_mode">
    <xsl:variable name="date">
      <xsl:for-each select="$node/mal:info/mal:revision">
        <xsl:sort select="@date" data-type="text" order="descending"/>
        <xsl:if test="position() = 1">
          <xsl:value-of select="@date"/>
        </xsl:if>
      </xsl:for-each>
    </xsl:variable>
    <xsl:variable name="revision"
                  select="$node/mal:info/mal:revision[@date = $date][last()]"/>
    <xsl:if test="$revision/@status != ''">
      <div class="version">
        <!-- FIXME: i18n -->
        <div class="title">
          <xsl:choose>
            <xsl:when test="$revision/@status = 'stub'">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Stub'"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:when test="$revision/@status = 'incomplete'">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Incomplete'"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:when test="$revision/@status = 'draft'">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Draft'"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:when test="$revision/@status = 'outdated'">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Outdated'"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:when test="$revision/@status = 'review'">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Ready for review'"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:when test="$revision/@status = 'candidate'">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Candidate'"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:when test="$revision/@status = 'final'">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Final'"/>
              </xsl:call-template>
            </xsl:when>
          </xsl:choose>
        </div>
        <p class="version">
          <!-- FIXME: i18n -->
          <xsl:text>Version </xsl:text>
          <xsl:value-of select="$revision/@version"/>
          <xsl:text> on </xsl:text>
          <xsl:value-of select="$revision/@date"/>
        </p>
        <xsl:apply-templates mode="mal2html.block.mode" select="$revision/*"/>
      </div>
    </xsl:if>
  </xsl:if>
</xsl:template>


<!-- == Matched Templates == -->

<xsl:template mode="html.title.mode" match="mal:page">
  <xsl:variable name="title" select="mal:info/mal:title[@type = 'text'][1]"/>
  <xsl:choose>
    <xsl:when test="$title">
      <xsl:value-of select="$title"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="mal:title"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template mode="html.header.mode" match="mal:page">
  <xsl:call-template name="mal2html.page.linktrails"/>
</xsl:template>

<xsl:template mode="html.footer.mode" match="mal:page">
  <xsl:call-template name="mal2html.page.copyrights"/>
</xsl:template>

<xsl:template mode="html.body.mode" match="mal:page">
  <xsl:call-template name="mal2html.editor.banner"/>
  <xsl:choose>
    <xsl:when test="not(mal:links[@type = 'next'])">
      <xsl:call-template name="mal2html.links.next"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:apply-templates
          select="mal:links[@type = 'next'][contains(concat(' ', @style, ' '), ' top ')]">
      </xsl:apply-templates>
    </xsl:otherwise>
  </xsl:choose>
  <xsl:apply-templates select="."/>
  <div class="clear"/>
</xsl:template>

<!-- = section = -->
<xsl:template mode="mal2html.section.mode" match="mal:section">
  <div id="{@id}">
    <xsl:attribute name="class">
      <xsl:text>sect</xsl:text>
      <xsl:if test="@ui:expanded">
        <xsl:text> ui-expander</xsl:text>
      </xsl:if>
    </xsl:attribute>
    <xsl:call-template name="mal2html.ui.expander.data"/>
    <div class="inner">
      <xsl:apply-templates select="."/>
    </div>
  </div>
</xsl:template>

<!-- page | section -->
<xsl:template match="mal:page | mal:section">
  <xsl:variable name="type" select="/mal:page/@type"/>
  <xsl:variable name="depth" select="count(ancestor::mal:section) + 1"/>
  <xsl:variable name="topiclinks">
    <xsl:if test="$type = 'guide'">
      <xsl:call-template name="mal.link.topiclinks"/>
    </xsl:if>
  </xsl:variable>
  <xsl:variable name="topicnodes" select="exsl:node-set($topiclinks)/*"/>
  <xsl:variable name="guidelinks">
    <xsl:call-template name="mal.link.guidelinks"/>
  </xsl:variable>
  <xsl:variable name="guidenodes" select="exsl:node-set($guidelinks)/*"/>
  <xsl:variable name="seealsolinks">
    <xsl:call-template name="mal.link.seealsolinks"/>
  </xsl:variable>
  <xsl:variable name="seealsonodes" select="exsl:node-set($seealsolinks)/*"/>
  <xsl:variable name="allgroups">
    <xsl:if test="$type = 'guide'">
      <xsl:text> </xsl:text>
      <xsl:for-each select="mal:links[@type = 'topic']">
        <xsl:choose>
          <xsl:when test="@groups">
            <xsl:value-of select="@groups"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:text>#default</xsl:text>
          </xsl:otherwise>
        </xsl:choose>
        <xsl:text> </xsl:text>
      </xsl:for-each>
    </xsl:if>
  </xsl:variable>
  <div class="hgroup">
    <xsl:apply-templates mode="mal2html.title.mode" select="mal:title"/>
    <xsl:apply-templates mode="mal2html.title.mode" select="mal:subtitle"/>
  </div>
  <div class="region">
  <div class="contents">
    <xsl:if test="$type = 'facets'">
      <xsl:call-template name="mal2html.facets.controls"/>
    </xsl:if>
    <xsl:for-each
        select="*[not(self::mal:section or self::mal:title or self::mal:subtitle)]">
      <xsl:choose>
        <xsl:when test="preceding-sibling::mal:section"/>
        <xsl:when test="self::mal:links[@type = 'topic']">
          <xsl:if test="$type = 'guide'">
            <xsl:apply-templates select=".">
              <xsl:with-param name="allgroups" select="$allgroups"/>
              <xsl:with-param name="links" select="$topicnodes"/>
            </xsl:apply-templates>
          </xsl:if>
        </xsl:when>
        <xsl:when test="self::mal:links[@type = 'guide']">
          <xsl:apply-templates select=".">
            <xsl:with-param name="links" select="$guidenodes"/>
          </xsl:apply-templates>
        </xsl:when>
        <xsl:when test="self::mal:links[@type = 'seealso']">
          <xsl:apply-templates select=".">
            <xsl:with-param name="links" select="$seealsonodes"/>
          </xsl:apply-templates>
        </xsl:when>
        <xsl:when test="self::mal:links[@type = 'next']">
          <xsl:if test="not(contains(concat(' ', @style, ' '), ' top '))">
            <xsl:apply-templates select="."/>
          </xsl:if>
        </xsl:when>
        <xsl:when test="self::mal:links">
          <xsl:apply-templates select="."/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:apply-templates mode="mal2html.block.mode" select="."/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:for-each>
    <xsl:if test="$type = 'guide'">
      <xsl:if test="not(mal:links[@type = 'topic'])">
        <xsl:call-template name="mal2html.links.topic">
          <xsl:with-param name="links" select="$topicnodes"/>
        </xsl:call-template>
      </xsl:if>
    </xsl:if>
    <xsl:if test="$type = 'gloss:glossary'">
      <xsl:call-template name="mal2html.gloss.terms"/>
    </xsl:if>
    <xsl:if test="$type = 'facets'">
      <xsl:call-template name="mal2html.facets.links"/>
    </xsl:if>
  </div>
  <xsl:apply-templates mode="mal2html.section.mode" select="mal:section"/>
  <xsl:variable name="postlinks" select="mal:section/following-sibling::mal:links"/>
  <xsl:if test="not(mal:section)">
    <xsl:if test="$guidenodes and not(mal:links[@type = 'guide'])">
      <xsl:call-template name="mal2html.links.guide">
        <xsl:with-param name="depth" select="$depth + 2"/>
        <xsl:with-param name="links" select="$guidenodes"/>
      </xsl:call-template>
    </xsl:if>
    <xsl:if test="$seealsonodes and not(mal:links[@type = 'seealso'])">
      <xsl:call-template name="mal2html.links.seealso">
        <xsl:with-param name="depth" select="$depth + 2"/>
        <xsl:with-param name="links" select="$seealsonodes"/>
      </xsl:call-template>
    </xsl:if>
  </xsl:if>
  <xsl:if test="($topicnodes and $postlinks[self::mal:links[@type = 'topic']]) or
                ($guidenodes and
                  ($postlinks[self::mal:links[@type = 'guide']] or
                    (mal:section and not(mal:links[@type = 'guide'])))) or
                ($seealsonodes and
                  ($postlinks[self::mal:links[@type = 'seealso']] or
                    (mal:section and not(mal:links[@type = 'seealso']))))
                ">
    <div class="sect sect-links">
      <div class="hgroup">
        <xsl:variable name="depth_">
          <xsl:choose>
            <xsl:when test="$depth + 1 &lt; 6">
              <xsl:value-of select="$depth + 1"/>
            </xsl:when>
            <xsl:otherwise>
              <xsl:value-of select="6"/>
            </xsl:otherwise>
          </xsl:choose>
        </xsl:variable>
        <xsl:element name="{concat('h', $depth_)}" namespace="{$html.namespace}">
          <span class="title">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Further Reading'"/>
            </xsl:call-template>
          </span>
        </xsl:element>
      </div>
      <div class="contents">
        <xsl:for-each select="$postlinks">
          <xsl:choose>
            <xsl:when test="self::mal:links[@type = 'topic']">
              <xsl:if test="$type = 'guide'">
                <xsl:apply-templates select=".">
                  <xsl:with-param name="depth" select="$depth + 2"/>
                  <xsl:with-param name="allgroups" select="$allgroups"/>
                  <xsl:with-param name="links" select="$topicnodes"/>
                </xsl:apply-templates>
              </xsl:if>
            </xsl:when>
            <xsl:when test="self::mal:links[@type = 'guide']">
              <xsl:apply-templates select=".">
                <xsl:with-param name="depth" select="$depth + 2"/>
                <xsl:with-param name="links" select="$guidenodes"/>
              </xsl:apply-templates>
            </xsl:when>
            <xsl:when test="self::mal:links[@type = 'seealso']">
              <xsl:apply-templates select=".">
                <xsl:with-param name="depth" select="$depth + 2"/>
                <xsl:with-param name="links" select="$seealsonodes"/>
              </xsl:apply-templates>
            </xsl:when>
            <xsl:when test="self::mal:links[@type = 'next']">
              <xsl:if test="not(contains(concat(' ', @style, ' '), ' top '))">
                <xsl:apply-templates select=".">
                  <xsl:with-param name="depth" select="$depth + 2"/>
                </xsl:apply-templates>
              </xsl:if>
            </xsl:when>
            <xsl:otherwise>
              <xsl:apply-templates select=".">
                <xsl:with-param name="depth" select="$depth + 2"/>
              </xsl:apply-templates>
            </xsl:otherwise>
          </xsl:choose>
        </xsl:for-each>
        <xsl:if test="$guidenodes and not(mal:links[@type = 'guide'])">
          <xsl:call-template name="mal2html.links.guide">
            <xsl:with-param name="depth" select="$depth + 2"/>
            <xsl:with-param name="links" select="$guidenodes"/>
          </xsl:call-template>
        </xsl:if>
        <xsl:if test="$seealsonodes and not(mal:links[@type = 'seealso'])">
          <xsl:call-template name="mal2html.links.seealso">
            <xsl:with-param name="depth" select="$depth + 2"/>
            <xsl:with-param name="links" select="$seealsonodes"/>
          </xsl:call-template>
        </xsl:if>
      </div>
    </div>
  </xsl:if>
  </div>
</xsl:template>


<!--%%==========================================================================
mal2html.title.mode
FIXME

FIXME
-->
<!-- = subtitle = -->
<xsl:template mode="mal2html.title.mode" match="mal:subtitle">
  <xsl:variable name="depth"
                select="count(ancestor::mal:section) + 2"/>
  <xsl:variable name="depth_">
    <xsl:choose>
      <xsl:when test="$depth &lt; 6">
        <xsl:value-of select="$depth"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="6"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:element name="{concat('h', $depth_)}" namespace="{$html.namespace}">
    <xsl:attribute name="class">
      <xsl:text>subtitle</xsl:text>
    </xsl:attribute>
    <xsl:apply-templates mode="mal2html.inline.mode"/>
  </xsl:element>
</xsl:template>

<!-- = title = -->
<xsl:template mode="mal2html.title.mode" match="mal:title">
  <xsl:variable name="depth"
                select="count(ancestor::mal:section) + 1"/>
  <xsl:variable name="depth_">
    <xsl:choose>
      <xsl:when test="$depth &lt; 6">
        <xsl:value-of select="$depth"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="6"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:element name="{concat('h', $depth_)}" namespace="{$html.namespace}">
    <xsl:attribute name="class">
      <xsl:text>title</xsl:text>
    </xsl:attribute>
    <span class="title">
      <xsl:apply-templates mode="mal2html.inline.mode"/>
    </span>
  </xsl:element>
</xsl:template>

<!--%# html.css.mode -->
<xsl:template mode="html.css.mode" match="mal:page">
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
span.link-button a {
  display: inline-block;
  background-color: </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
  color: </xsl:text>
    <xsl:value-of select="$color.background"/><xsl:text>;
  text-shadow: </xsl:text>
    <xsl:value-of select="$color.link"/><xsl:text> 1px 1px 0px;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.link"/><xsl:text>;
  padding: 0.2em 0.5em 0.2em 0.5em;
  -moz-border-radius: 2px;
  -webkit-border-radius: 2px;
  border-radius: 2px;
}
span.link-button a:visited {
  color: </xsl:text>
    <xsl:value-of select="$color.background"/><xsl:text>;
}
span.link-button a:hover {
  text-decoration: none;
  color: </xsl:text>
    <xsl:value-of select="$color.background"/><xsl:text>;
}
div.floatleft {
  float: left;
  margin-right: 1em;
}
div.floatright {
  float: right;
  margin-left: 1em;
}
div.floatstart {
  float: </xsl:text><xsl:value-of select="$left"/><xsl:text>;
  margin-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 1em;
}
div.floatend {
  float: </xsl:text><xsl:value-of select="$right"/><xsl:text>;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1em;
}

div.copyrights {
  text-align: center;
  color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
}

div.mouseovers {
  width: 250px;
  height: 200px;
  text-align: center;
  margin: 0;
  margin-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 1em;
  float: </xsl:text><xsl:value-of select="$left"/><xsl:text>;
}
ul.mouseovers li { margin: 0; }
ul.mouseovers a {
  display: block;
  padding: 4px;
}
ul.mouseovers a:hover {
  background: </xsl:text><xsl:value-of select="$color.blue_background"/><xsl:text>;
  text-decoration: none;
}
ul.mouseovers a img {
  display: none;
  position: absolute;
  margin: 0; padding: 0;
}

table.toronto {
  clear: both;
  width: 100%;
}
table.toronto td {
  padding-top: 1em;
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 0;
  padding-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 0.83em;
  width: 33%;
}
div.toronto-link {
  margin: 0;
  font-weight: bold;
}
div.toronto-desc {
  margin: 0;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}

table.twocolumn { width: 100%; }
td.twocolumnleft { width: 48%; vertical-align: top; padding: 0; margin: 0; }
td.twocolumnright {
  width: 52%; vertical-align: top;
  margin: 0; padding: 0;
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1em;
}

div.links .desc a {
  color: inherit;
}
div.links .desc a:hover {
  color: </xsl:text><xsl:value-of select="$color.link"/><xsl:text>;
}
a.bold { font-weight: bold; }
a.linkdiv {
  display: block;
  margin: 0;
  padding: 0.5em;
}
a.linkdiv:hover {
  text-decoration: none;
  background-color: </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
  outline: solid 1px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
}
a.linkdiv > span.title {
  display: block;
  margin: 0;
  font-size: 1em;
  font-weight: bold;
  color: inherit;
}
a.linkdiv > span.desc {
  display: block;
  margin: 0.2em 0 0 0;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
span.linkdiv-dash { display: none; }

div.example {
  border-</xsl:text><xsl:value-of select="$left"/><xsl:text>: solid 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1em;
}

div.comment {
  padding: 0.5em;
  border: solid 2px </xsl:text>
    <xsl:value-of select="$color.red_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.red_background"/><xsl:text>;
}
div.comment div.comment {
  margin: 1em 1em 0 1em;
}
div.comment div.cite {
  margin: 0 0 0.5em 0;
  font-style: italic;
}

div.tree > div.inner > div.title { margin-bottom: 0.5em; }
ul.tree {
  margin: 0; padding: 0;
  list-style-type: none;
}
li.tree { margin: -2px 0 0 0; padding: 0; }
li.tree div { margin: 0; padding: 0; }
ul.tree ul.tree {
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.44em;
}
div.tree-lines ul.tree { margin-left: 0; }

span.hi {
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
}

div.facets {
  display: inline-block;
  padding: 6px;
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
} 
div.facet {
 vertical-align: top;
  display: inline-block;
  margin-top: 0;
  margin-bottom: 1em;
  margin-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 1em;
}
div.facet div.title { margin: 0; }
div.facet li {
  margin: 0; padding: 0;
  list-style-type: none;
}
div.facet input {
  vertical-align: middle;
  margin: 0;
}
dt.gloss-term {
  margin-top: 1.2em;
  font-weight: bold;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
dt.gloss-term:first-child, dt.gloss-term + dt.gloss-term { margin-top: 0; }
dt.gloss-term + dd { margin-top: 0.2em; }
dd.gloss-link {
  margin: 0 0.2em 0 0.2em;
  border-</xsl:text><xsl:value-of select="$left"/><xsl:text>: solid 4px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1em;
}
dd.gloss-def {
  margin: 0 0.2em 1em 0.2em;
  border-</xsl:text><xsl:value-of select="$left"/><xsl:text>: solid 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1em;
}
a.gloss-term {
  tabindex: 0;
  border-bottom: dashed 1px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
}
a.gloss-term:hover {
  text-decoration: none;
  border-bottom-style: solid;
}
span.gloss-desc {
  display: none;
  position: absolute;
  margin: 0;
  padding: 0.2em 0.5em 0.2em 0.5em;
  max-width: 24em;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.yellow_border"/><xsl:text>;
  -moz-box-shadow: 2px 2px 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  -webkit-box-shadow: 2px 2px 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  box-shadow: 2px 2px 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
</xsl:text>
<xsl:if test="$mal2html.editor_mode">
<xsl:text>
div.version {
  position: absolute;
  </xsl:text><xsl:value-of select="$right"/><xsl:text>: 12px;
  opacity: 0.2;
  margin-top: -1em;
  padding: 0.5em 1em 0.5em 1em;
  max-width: 24em;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
}
div.version:hover { opacity: 0.8; }
div.version p.version { margin-top: 0.2em; }
span.status {
  font-size: 0.83em;
  font-weight: normal;
  padding-left: 0.2em;
  padding-right: 0.2em;
  color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.red_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
}
span.status-stub, span.status-draft, span.status-incomplete, span.status-outdated { background-color: </xsl:text>
  <xsl:value-of select="$color.red_background"/><xsl:text>; }
</xsl:text>
</xsl:if>
</xsl:template>

<!--%# html.js.mode -->
<xsl:template mode="html.js.mode" match="mal:page">
  <xsl:call-template name="mal2html.facets.js"/>
  <xsl:call-template name="mal2html.gloss.js"/>
<xsl:text><![CDATA[
$(document).ready(function () {
  $('div.mouseovers').each(function () {
    var contdiv = $(this);
    var width = 0;
    var height = 0;
    contdiv.find('img').each(function () {
      if ($(this).attr('data-yelp-match') == '')
        $(this).show();
    });
    contdiv.next('ul').find('a').each(function () {
      var mlink = $(this);
      mlink.hover(
        function () {
          var offset = contdiv.offset();
          mlink.find('img').css({left: offset.left, top: offset.top, zIndex: 10});
          mlink.find('img').fadeIn('fast');
        },
        function () {
          mlink.find('img').fadeOut('fast');
        }
      );
    });
  });
});
]]></xsl:text>
</xsl:template>

</xsl:stylesheet>
